"""Google OIDC and opaque server-side sessions, separate from knowledge storage."""
import asyncio
from contextlib import contextmanager
import base64
from dataclasses import dataclass, field
import hashlib
import hmac
import logging
import os
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import urlencode, urlparse
import uuid

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.id_token import verify_oauth2_token
import httpx

SESSION_COOKIE = "jst_session"
FLOW_COOKIE = "jst_google_flow"
FLOW_TTL = 600
IDLE_TTL = 1800
SESSION_TTL = 28800

logger = logging.getLogger(__name__)

def auth_json(content, status_code=200, headers=None):
    return JSONResponse(content,status_code=status_code,headers={**(headers or {}),'Cache-Control':'no-store'})


class GoogleLoginError(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)

class LoginCapacityError(Exception):
    pass

def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def emails(value: str) -> frozenset[str]:
    return frozenset(v.strip().casefold() for v in value.split(',') if v.strip())

@dataclass(frozen=True)
class AuthSettings:
    client_id: str
    client_secret: str = field(repr=False)
    public_url: str
    redirect_uri: str
    developer_emails: frozenset[str]
    allowed_emails: frozenset[str]
    database: Path

    @classmethod
    def from_env(cls):
        return cls(os.getenv('GOOGLE_CLIENT_ID', '').strip(), os.getenv('GOOGLE_CLIENT_SECRET', '').strip(),
            os.getenv('AUTH_PUBLIC_URL', 'http://localhost:3000').rstrip('/'),
            os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8000/api/auth/google/callback').strip(),
            emails(os.getenv('AUTH_DEVELOPER_EMAILS', '')), emails(os.getenv('AUTH_ALLOWED_EMAILS', '')),
            Path(__file__).resolve().parent.parent / 'data' / 'auth.sqlite')

    @property
    def secure(self):
        return urlparse(self.public_url).scheme == 'https'

    @property
    def ready(self):
        front, callback = urlparse(self.public_url), urlparse(self.redirect_uri)
        valid_urls = all(u.scheme == 'https' or (u.scheme == 'http' and u.hostname in {'localhost', '127.0.0.1'}) for u in (front, callback))
        return bool(self.client_id and self.client_secret and valid_urls and front.hostname and front.hostname == callback.hostname
            and not front.username and not callback.username and not front.query and not front.fragment
            and front.path in {'', '/'} and callback.path == '/api/auth/google/callback'
            and not callback.query and not callback.fragment and front.scheme == callback.scheme)

    @property
    def session_cookie(self):
        return '__Host-' + SESSION_COOKIE if self.secure else SESSION_COOKIE

    @property
    def flow_cookie(self):
        return '__Host-' + FLOW_COOKIE if self.secure else FLOW_COOKIE

    def allows(self, email: str, authoritative: bool = False):
        return not self.allowed_emails or (authoritative and email.casefold() in self.allowed_emails | self.developer_emails)

    def is_developer(self, session):
        return bool(session.get('google_authoritative')) and session['email'].casefold() in self.developer_emails


def google_authoritative(claims):
    # Google does not vouch for current ownership of third-party email addresses
    # without a Workspace hosted-domain claim, even if email_verified is true.
    return claims.get('email_verified') is True and (
        str(claims.get('email','')).casefold().endswith('@gmail.com')
        or isinstance(claims.get('hd'),str) and bool(claims['hd'].strip()))


class AuthStore:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        with self.connect() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] > 3:
                raise RuntimeError('Unsupported account database version')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS auth_users (
                    id TEXT PRIMARY KEY, provider TEXT NOT NULL, subject TEXT NOT NULL,
                    email TEXT NOT NULL, name TEXT NOT NULL, created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL, UNIQUE(provider, subject));
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    session_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    csrf TEXT NOT NULL, created_at INTEGER NOT NULL, last_seen INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_flows (
                    state_hash TEXT PRIMARY KEY, browser_hash TEXT NOT NULL,
                    nonce TEXT NOT NULL, verifier TEXT NOT NULL, expires_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_rate_limits (
                    actor_hash TEXT PRIMARY KEY, hits INTEGER NOT NULL, expires_at INTEGER NOT NULL);
            ''')
            db.execute('BEGIN IMMEDIATE')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(auth_users)')}
            if 'google_authoritative' not in columns:
                db.execute('ALTER TABLE auth_users ADD COLUMN google_authoritative INTEGER NOT NULL DEFAULT 0')
                db.execute("UPDATE auth_users SET google_authoritative=1 WHERE lower(email) LIKE '%@gmail.com'")
            flow_columns = {row['name'] for row in db.execute('PRAGMA table_info(auth_flows)')}
            if 'intent' not in flow_columns:
                # Old in-flight OAuth requests may only log into existing accounts.
                db.execute("ALTER TABLE auth_flows ADD COLUMN intent TEXT NOT NULL DEFAULT 'login'")
            db.execute('PRAGMA user_version = 3')

    def rate_limit(self, actor: str, limit: int, window: int = 60):
        now = int(time.time())
        key = digest(actor)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM auth_rate_limits WHERE expires_at <= ?', (now,))
            row = db.execute('SELECT hits FROM auth_rate_limits WHERE actor_hash=?', (key,)).fetchone()
            if row and row['hits'] >= limit:
                return False
            db.execute('INSERT INTO auth_rate_limits VALUES (?,?,?) ON CONFLICT(actor_hash) DO UPDATE SET hits=hits+1', (key,1,now+window))
        return True

    def create_flow(self, intent: str = 'login'):
        if intent not in {'login', 'register'}:
            raise ValueError('Unsupported authentication intent')
        state, browser, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(4))
        now = int(time.time())
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM auth_flows WHERE expires_at <= ?', (now,))
            db.execute('DELETE FROM auth_sessions WHERE expires_at <= ? OR last_seen <= ?', (now, now-IDLE_TTL))
            if db.execute('SELECT COUNT(*) FROM auth_flows').fetchone()[0] >= 100:
                raise LoginCapacityError()
            db.execute('INSERT INTO auth_flows (state_hash,browser_hash,nonce,verifier,expires_at,intent) VALUES (?,?,?,?,?,?)', (digest(state), digest(browser), nonce, verifier, now+FLOW_TTL, intent))
        return state, browser, nonce, verifier

    def consume_flow(self, state: str, browser: str):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM auth_flows WHERE state_hash=?', (digest(state),)).fetchone()
            if row is None or not browser or not hmac.compare_digest(row['browser_hash'], digest(browser)):
                return None
            db.execute('DELETE FROM auth_flows WHERE state_hash=?', (digest(state),))
            return dict(row) if row['expires_at'] > time.time() else None

    def create_session(self, claims, previous: str = '', *, intent: str = 'login'):
        if intent not in {'login', 'register'}:
            raise ValueError('Unsupported authentication intent')
        now = int(time.time())
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute("SELECT id,email,google_authoritative FROM auth_users WHERE provider='google' AND subject=?", (claims['sub'],)).fetchone()
            if intent == 'login' and existing is None:
                raise GoogleLoginError('not_registered')
            if intent == 'register' and existing is not None:
                raise GoogleLoginError('already_registered')
            authoritative = int(google_authoritative(claims))
            if existing and (existing['email'] != claims['email'].casefold() or existing['google_authoritative'] != authoritative):
                db.execute('DELETE FROM auth_sessions WHERE user_id=?', (existing['id'],))
            db.execute('''INSERT INTO auth_users (id,provider,subject,email,name,created_at,updated_at,google_authoritative) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(provider,subject) DO UPDATE SET email=excluded.email,
                name=excluded.name,updated_at=excluded.updated_at,google_authoritative=excluded.google_authoritative''',
                (str(uuid.uuid4()), 'google', claims['sub'], claims['email'].casefold(), str(claims.get('name', ''))[:160], now, now, authoritative))
            user_id = db.execute("SELECT id FROM auth_users WHERE provider='google' AND subject=?", (claims['sub'],)).fetchone()['id']
            if previous:
                db.execute('DELETE FROM auth_sessions WHERE session_hash=?', (digest(previous),))
            db.execute('INSERT INTO auth_sessions VALUES (?,?,?,?,?,?)', (digest(token), user_id, csrf, now, now, now+SESSION_TTL))
        return token

    def session(self, token: str):
        if not token or len(token) > 512:
            return None
        now = int(time.time())
        with self.connect() as db:
            row = db.execute('''SELECT u.id,u.email,u.name,u.google_authoritative,s.csrf,s.last_seen,s.expires_at
                FROM auth_sessions s JOIN auth_users u ON s.user_id=u.id WHERE s.session_hash=?''', (digest(token),)).fetchone()
            if row is None:
                return None
            if now >= row['expires_at'] or now-row['last_seen'] >= IDLE_TTL:
                db.execute('DELETE FROM auth_sessions WHERE session_hash=?', (digest(token),))
                return None
            db.execute('UPDATE auth_sessions SET last_seen=? WHERE session_hash=?', (now,digest(token)))
            return dict(row)

    def revoke(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM auth_sessions WHERE session_hash=?', (digest(token),))


async def google_identity(code: str, verifier: str, nonce: str, settings: AuthSettings):
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        response = await client.post('https://oauth2.googleapis.com/token', data={
            'code':code, 'client_id':settings.client_id, 'client_secret':settings.client_secret,
            'redirect_uri':settings.redirect_uri, 'grant_type':'authorization_code', 'code_verifier':verifier})
        if response.is_error:
            try:
                provider_error = response.json().get('error', '')
            except ValueError:
                provider_error = ''
            reason = {'invalid_client':'invalid_client', 'invalid_grant':'invalid_grant',
                'redirect_uri_mismatch':'redirect_mismatch'}.get(provider_error, 'token_exchange_failed')
            raise GoogleLoginError(reason)
        token = response.json().get('id_token')
    if not isinstance(token, str):
        raise GoogleLoginError('missing_id_token')
    def verify():
        transport = GoogleRequest()
        def bounded_request(*args, **kwargs):
            kwargs['timeout'] = 10
            return transport(*args, **kwargs)
        return verify_oauth2_token(token, bounded_request, audience=settings.client_id, clock_skew_in_seconds=30)
    try:
        claims = await asyncio.to_thread(verify)
    except Exception as error:
        # Classify known verifier errors locally; never log their raw messages,
        # which can contain token claims, key IDs or other provider details.
        detail = str(error).casefold()
        if 'too early' in detail or 'issued in the future' in detail:
            reason = 'server_clock'
        elif 'expired' in detail:
            reason = 'token_expired'
        elif 'audience' in detail:
            reason = 'invalid_audience'
        elif 'issuer' in detail:
            reason = 'invalid_issuer'
        elif 'signature' in detail:
            reason = 'invalid_signature'
        elif 'certificate' in detail or 'public key' in detail:
            reason = 'certificate_unavailable'
        else:
            reason = 'invalid_id_token'
        logger.warning("Google sign-in token verification failed: %s (%s)", reason, type(error).__name__)
        raise GoogleLoginError(reason) from None
    try:
        return validate_identity(claims, nonce, settings)
    except ValueError:
        raise GoogleLoginError('invalid_identity') from None


def validate_identity(claims: dict, nonce: str, settings: AuthSettings):
    if (not isinstance(claims.get('nonce'), str) or not hmac.compare_digest(claims['nonce'], nonce)
        or not isinstance(claims.get('sub'), str) or not claims['sub'] or len(claims['sub']) > 255
        or claims.get('email_verified') is not True or not isinstance(claims.get('email'), str)
        or '@' not in claims['email'] or len(claims['email']) > 320):
        raise ValueError('Invalid identity claims')
    email = claims['email'].casefold()
    if not settings.allows(email, google_authoritative(claims)):
        raise PermissionError('Account not invited')
    return claims



class LimitedBodyMiddleware:
    """Bound decoded request bodies before JSON/multipart parsers allocate them."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope.get('path','').startswith('/api/') or scope['method'] in {'GET','HEAD','OPTIONS'}:
            return await self.app(scope,receive,send)
        upload = scope['path'] in {'/api/rag/ingest-pdf','/api/rag/ingest-excel'}
        limit = 21*1024*1024 if upload else 1024*1024
        headers = dict(scope.get('headers',[]))
        try:
            length = int(headers.get(b'content-length',b'0'))
            if length < 0: raise ValueError()
        except ValueError:
            return await JSONResponse({'detail':'Ukuran request tidak valid.'},status_code=400)(scope,receive,send)
        if length > limit:
            return await JSONResponse({'detail':'Request terlalu besar.'},status_code=413)(scope,receive,send)
        payload=bytearray()
        size=0
        while True:
            message=await receive()
            if message['type']=='http.disconnect': return
            chunk=message.get('body',b'')
            size+=len(chunk)
            if size>limit:
                return await JSONResponse({'detail':'Request terlalu besar.'},status_code=413)(scope,receive,send)
            payload.extend(chunk)
            if not message.get('more_body',False): break
        payload=bytes(payload)
        delivered=False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {'type':'http.request','body':payload,'more_body':False}
            return await receive()
        return await self.app(scope,replay,send)


def install_auth(app: FastAPI, settings: AuthSettings | None = None, store: AuthStore | None = None):
    settings = settings or AuthSettings.from_env()
    store = store or AuthStore(settings.database)
    store.initialize()
    app.add_middleware(LimitedBodyMiddleware)
    router = APIRouter(prefix='/api/auth')
    public_routes = {('/api/auth/session','GET'),('/api/auth/google/login','GET'),('/api/auth/google/register','GET'),('/api/auth/google/callback','GET')}
    chat_routes = {('/api/chat','POST'),('/api/chat/stream','POST'),('/api/health','GET')}

    @app.middleware('http')
    async def authenticate(request: Request, call_next):
        path = request.url.path
        if path == '/api/auth/google/callback':
            request.state.oauth_query = dict(request.query_params)
            request.scope['query_string'] = b''  # Keep codes/state out of access logs.
        # All API routes require a session unless explicitly listed above.
        if request.method == 'OPTIONS':
            return await call_next(request)
        if path.startswith('/api/') and (path,request.method) not in public_routes:
            if not settings.ready:
                return auth_json({'detail':'Login Google belum dikonfigurasi.'}, status_code=503, headers={'Cache-Control':'no-store'})
            session = store.session(request.cookies.get(settings.session_cookie, ''))
            if session and not settings.allows(session['email'], bool(session['google_authoritative'])):
                store.revoke(request.cookies.get(settings.session_cookie,''))
                session = None
            if session is None:
                return auth_json({'detail':'Silakan masuk dengan Google.'}, status_code=401, headers={'Cache-Control':'no-store'})
            developer = settings.is_developer(session)
            if (path,request.method) not in chat_routes | {('/api/auth/logout','POST')} and not developer:
                return auth_json({'detail':'Hanya akun developer yang dapat mengakses fitur ini.'}, status_code=403)
            if request.method not in {'GET','HEAD'}:
                csrf = request.headers.get('x-csrf-token','')
                if request.headers.get('origin') != settings.public_url or not csrf.isascii() or not hmac.compare_digest(csrf,session['csrf']):
                    return auth_json({'detail':'Permintaan tidak valid. Muat ulang halaman.'},status_code=403)
            limit = 10 if path in {'/api/chat','/api/chat/stream'} else 120
            bucket = 'chat' if path in {'/api/chat','/api/chat/stream'} else 'api'
            if path != '/api/auth/logout' and not store.rate_limit(bucket + ':' + session['id'],limit):
                return auth_json({'detail':'Terlalu banyak permintaan. Coba lagi sebentar.'},status_code=429,headers={'Retry-After':'60','Cache-Control':'no-store'})
            request.state.auth_user = session
        elif path in {'/docs','/redoc','/openapi.json'}:
            session = store.session(request.cookies.get(settings.session_cookie,''))
            if not settings.ready or not session or not settings.is_developer(session):
                return auth_json({'detail':'Akses developer diperlukan.'},status_code=403)
        response = await call_next(request)
        if path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @router.get('/session')
    async def current_session(request: Request):
        peer = request.client.host if request.client else 'unknown'
        if not store.rate_limit('session:' + peer,120):
            return auth_json({'detail':'Terlalu banyak pemeriksaan sesi.'},status_code=429,headers={'Retry-After':'60','Cache-Control':'no-store'})
        session = store.session(request.cookies.get(settings.session_cookie,'')) if settings.ready else None
        if session and not settings.allows(session['email'], bool(session['google_authoritative'])):
            store.revoke(request.cookies.get(settings.session_cookie,''))
            session = None
        user = None if not session else {'id':session['id'], 'email':session['email'],
            'name':session['name'], 'role':'developer' if settings.is_developer(session) else 'user'}
        return {'configured':settings.ready, 'user':user, 'csrf_token':session['csrf'] if session else None}

    def set_cookie(response, name, value, age):
        response.set_cookie(name, value, max_age=age, httponly=True, secure=settings.secure, samesite='lax', path='/')

    def failure(reason):
        response = RedirectResponse(settings.public_url + '/?auth_error=' + reason, status_code=303)
        response.delete_cookie(settings.flow_cookie, path='/', secure=settings.secure, httponly=True, samesite='lax')
        return response

    async def start_google(request: Request, intent: str):
        peer = request.client.host if request.client else 'unknown'
        if not store.rate_limit('login:' + peer,20):
            return auth_json({'detail':'Terlalu banyak percobaan login. Coba lagi sebentar.'},status_code=429,headers={'Retry-After':'60','Cache-Control':'no-store'})
        if not settings.ready:
            return auth_json({'detail':'Login Google belum dikonfigurasi.'},status_code=503)
        try:
            state, browser, nonce, verifier = store.create_flow(intent)
        except LoginCapacityError:
            return auth_json({'detail':'Terlalu banyak proses login. Coba lagi sebentar.'},status_code=429,headers={'Retry-After':'60'})
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        query = urlencode({'client_id':settings.client_id, 'redirect_uri':settings.redirect_uri,
            'response_type':'code','scope':'openid email profile','state':state,'nonce':nonce,
            'code_challenge':challenge,'code_challenge_method':'S256','prompt':'select_account consent' if intent == 'register' else 'select_account'})
        response = RedirectResponse('https://accounts.google.com/o/oauth2/v2/auth?' + query, status_code=302)
        set_cookie(response,settings.flow_cookie,browser,FLOW_TTL)
        return response

    @router.get('/google/login')
    async def login(request: Request):
        return await start_google(request, 'login')

    @router.get('/google/register')
    async def register(request: Request):
        return await start_google(request, 'register')

    @router.get('/google/callback')
    async def callback(request: Request):
        if not settings.ready:
            return failure('not_configured')
        query = request.state.oauth_query
        state = query.get('state','')
        flow = store.consume_flow(state,request.cookies.get(settings.flow_cookie,'')) if state and len(state)<512 else None
        if flow is None:
            return failure('invalid_state')
        if query.get('error'):
            return failure('cancelled')
        code = query.get('code','')
        if not code or len(code)>4096:
            return failure('failed')
        try:
            claims = await google_identity(code,flow['verifier'],flow['nonce'],settings)
            token = store.create_session(claims,request.cookies.get(settings.session_cookie,''), intent=flow['intent'])
        except PermissionError:
            return failure('not_allowed')
        except GoogleLoginError as error:
            logger.warning("Google sign-in failed: %s", error.reason)
            return failure(error.reason)
        except httpx.RequestError:
            logger.warning("Google sign-in failed: provider connection unavailable")
            return failure('google_unreachable')
        except Exception as error:
            # Never log the exception message, URL, response body, code or token.
            logger.warning("Google sign-in failed (%s)", type(error).__name__)
            return failure('failed')
        response = RedirectResponse(settings.public_url+'/',status_code=303)
        set_cookie(response,settings.session_cookie,token,SESSION_TTL)
        response.delete_cookie(settings.flow_cookie,path='/',secure=settings.secure,httponly=True,samesite='lax')
        return response

    @router.post('/logout')
    async def logout(request: Request):
        store.revoke(request.cookies.get(settings.session_cookie,''))
        response = auth_json({'ok':True})
        response.delete_cookie(settings.session_cookie,path='/',secure=settings.secure,httponly=True,samesite='lax')
        return response

    app.include_router(router)
    return settings, store
