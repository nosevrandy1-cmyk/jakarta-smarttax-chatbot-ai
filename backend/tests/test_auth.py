"""Authentication tests use a temporary account database and mocked Google exchange."""
import asyncio
import json
from types import SimpleNamespace
from dataclasses import replace
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
import httpx
from app.auth import (AuthSettings, AuthStore, SESSION_COOKIE, FLOW_COOKIE, IDLE_TTL,
    SESSION_TTL, digest, install_auth, validate_identity, google_identity)


class GoogleAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jst-auth-tests-')
        self.settings = AuthSettings('test-client', 'test-secret', 'http://localhost:3000',
            'http://localhost:8000/api/auth/google/callback',frozenset({'developer@example.test'}),frozenset(),Path(self.temp.name)/'auth.sqlite')
        self.store = AuthStore(self.settings.database)
        self.app = FastAPI()
        install_auth(self.app,self.settings,self.store)
        @self.app.post('/api/chat/stream')
        async def chat(): return {'ok':True}
        @self.app.get('/api/rag/telemetry')
        async def telemetry(): return {'ok':True}
        @self.app.post('/api/rag/ingest-pdf')
        async def upload(): return {'ok':True}
        @self.app.post('/api/eval/run')
        async def evaluate(): return {'ok':True}
        self.claims={'sub':'stable-subject','email':'user@example.test','name':'Test User','email_verified':True,'nonce':'test-nonce'}

    def tearDown(self): self.temp.cleanup()

    def run_async(self,fn):
        async def execute():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='http://localhost:8000') as client:
                await fn(client)
        asyncio.run(execute())

    def test_anonymous_cannot_call_chat_or_dashboard_api(self):
        async def check(client):
            self.assertEqual((await client.post('/api/chat/stream')).status_code,401)
            self.assertEqual((await client.get('/api/rag/telemetry')).status_code,401)
            self.assertEqual((await client.get('/api/auth/session')).json()['user'],None)
        self.run_async(check)

    def test_missing_configuration_fails_closed(self):
        app=FastAPI()
        install_auth(app,replace(self.settings,client_secret=''),self.store)
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8000') as c:
                self.assertFalse((await c.get('/api/auth/session')).json()['configured'])
                self.assertEqual((await c.post('/api/chat/stream')).status_code,503)
                self.assertEqual((await c.get('/api/auth/google/login')).status_code,503)
        asyncio.run(check())

    def test_login_includes_state_nonce_and_pkce_only_identity_scopes(self):
        async def check(client):
            response=await client.get('/api/auth/google/login')
            self.assertEqual(response.status_code,302)
            query=parse_qs(urlparse(response.headers['location']).query)
            self.assertEqual(query['scope'],['openid email profile'])
            self.assertEqual(query['code_challenge_method'],['S256'])
            self.assertTrue(query['state'][0]);self.assertTrue(query['nonce'][0])
            self.assertIn('HttpOnly',response.headers['set-cookie'])
            self.assertNotIn('test-secret',response.headers['location'])
        self.run_async(check)

    def test_callback_requires_browser_cookie_and_is_single_use(self):
        state,browser,nonce,_=self.store.create_flow()
        claims={**self.claims,'nonce':nonce}
        async def check(client):
            with patch('app.auth.google_identity',new=AsyncMock(return_value=claims)) as exchange:
                rejected=await client.get('/api/auth/google/callback',params={'state':state,'code':'test-code'})
                self.assertIn('invalid_state',rejected.headers['location']);exchange.assert_not_called()
                client.cookies.set(FLOW_COOKIE,browser)
                response=await client.get('/api/auth/google/callback',params={'state':state,'code':'test-code'})
                self.assertEqual(response.headers['location'],'http://localhost:3000/')
                session=(await client.get('/api/auth/session')).json()
                self.assertEqual(session['user']['role'],'user')
                self.assertTrue(session['csrf_token'])
                repeated=await client.get('/api/auth/google/callback',params={'state':state,'code':'test-code'})
                self.assertIn('invalid_state',repeated.headers['location'])
                self.assertEqual(exchange.await_count,1)
        self.run_async(check)

    def test_user_cannot_call_developer_endpoints_or_spoof_role(self):
        token=self.store.create_session(self.claims)
        async def check(client):
            client.cookies.set(SESSION_COOKIE,token)
            self.assertEqual((await client.get('/api/rag/telemetry',headers={'X-Role':'developer'})).status_code,403)
            self.assertEqual((await client.post('/api/rag/ingest-pdf')).status_code,403)
            self.assertEqual((await client.post('/api/eval/run')).status_code,403)
            self.assertEqual((await client.get('/openapi.json')).status_code,403)
        self.run_async(check)

    def test_csrf_and_origin_required_and_logout_revokes_session(self):
        token=self.store.create_session(self.claims)
        csrf=self.store.session(token)['csrf']
        async def check(client):
            client.cookies.set(SESSION_COOKIE,token)
            self.assertEqual((await client.post('/api/chat/stream')).status_code,403)
            self.assertEqual((await client.post('/api/chat/stream',headers={'Origin':'https://attacker.test','X-CSRF-Token':csrf})).status_code,403)
            headers={'Origin':self.settings.public_url,'X-CSRF-Token':csrf}
            self.assertEqual((await client.post('/api/chat/stream',headers=headers)).status_code,200)
            self.assertEqual((await client.post('/api/auth/logout',headers=headers)).status_code,200)
            self.assertIsNone(self.store.session(token))
            client.cookies.set(SESSION_COOKIE,token)
            self.assertEqual((await client.post('/api/chat/stream',headers=headers)).status_code,401)
        self.run_async(check)

    def test_developer_has_management_access(self):
        token=self.store.create_session({**self.claims,'email':'developer@example.test','hd':'example.test'})
        async def check(client):
            client.cookies.set(SESSION_COOKIE,token)
            self.assertEqual((await client.get('/api/rag/telemetry')).status_code,200)
            session=(await client.get('/api/auth/session')).json()
            self.assertEqual(session['user']['role'],'developer')
            self.assertEqual((await client.post('/api/eval/run',headers={'Origin':self.settings.public_url,'X-CSRF-Token':session['csrf_token']})).status_code,200)
        self.run_async(check)

    def test_sessions_are_hashed_expire_idle_and_have_absolute_limit(self):
        token=self.store.create_session(self.claims)
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM auth_sessions').fetchone()
            self.assertEqual(row['session_hash'],digest(token));self.assertNotEqual(row['session_hash'],token)
            db.execute('UPDATE auth_sessions SET last_seen=?',(int(time.time())-IDLE_TTL,))
        self.assertIsNone(self.store.session(token))
        token=self.store.create_session(self.claims)
        with patch('app.auth.time.time',return_value=time.time()+SESSION_TTL+1):
            self.assertIsNone(self.store.session(token))

    def test_identity_uses_provider_sub_instead_of_email(self):
        first=self.store.create_session(self.claims)
        user_id=self.store.session(first)['id']
        second=self.store.create_session({**self.claims,'email':'changed@example.test'},first)
        self.assertEqual(self.store.session(second)['id'],user_id)
        self.assertIsNone(self.store.session(first))
        another=self.store.create_session({**self.claims,'sub':'different-subject'})
        self.assertNotEqual(self.store.session(another)['id'],user_id)

    def test_claims_require_nonce_verified_email_and_invitation(self):
        self.assertEqual(validate_identity(self.claims,'test-nonce',self.settings),self.claims)
        for changed in [{'nonce':'wrong'},{'email_verified':False},{'sub':''}]:
            with self.assertRaises(ValueError): validate_identity({**self.claims,**changed},'test-nonce',self.settings)
        with self.assertRaises(PermissionError):
            validate_identity(self.claims,'test-nonce',replace(self.settings,allowed_emails=frozenset({'invited@example.test'})))

    def test_expired_flow_and_cancelled_callback_create_no_session(self):
        state,browser,_,_=self.store.create_flow()
        with self.store.connect() as db: db.execute('UPDATE auth_flows SET expires_at=0')
        self.assertIsNone(self.store.consume_flow(state,browser))
        state,browser,_,_=self.store.create_flow()
        async def check(client):
            client.cookies.set(FLOW_COOKIE,browser)
            result=await client.get('/api/auth/google/callback',params={'state':state,'error':'access_denied'})
            self.assertIn('cancelled',result.headers['location'])
            self.assertIsNone((await client.get('/api/auth/session')).json()['user'])
        self.run_async(check)

    def test_production_urls_and_cookie_security(self):
        self.assertFalse(replace(self.settings,public_url='http://example.test').ready)
        self.assertFalse(replace(self.settings,public_url='https://',redirect_uri='https:///api/auth/google/callback').ready)
        settings=replace(self.settings,public_url='https://jst.example.test',redirect_uri='https://jst.example.test/api/auth/google/callback')
        self.assertTrue(settings.ready)
        self.assertTrue(settings.secure)

    def test_provider_verifier_receives_expected_audience_and_rejects_bad_tokens(self):
        token_response=httpx.Response(200,json={'id_token':'provider-test-token'},request=httpx.Request('POST','https://oauth2.googleapis.com/token'))
        with patch('app.auth.httpx.AsyncClient.post',new=AsyncMock(return_value=token_response)),patch('app.auth.verify_oauth2_token',return_value=self.claims) as verify:
            result=asyncio.run(google_identity('code','verifier','test-nonce',self.settings))
            self.assertEqual(result['sub'],'stable-subject')
            self.assertEqual(verify.call_args.kwargs['audience'],'test-client')
        for reason in ['wrong audience','expired','invalid signature','wrong issuer']:
            with patch('app.auth.httpx.AsyncClient.post',new=AsyncMock(return_value=token_response)),patch('app.auth.verify_oauth2_token',side_effect=ValueError(reason)):
                with self.assertRaises(ValueError): asyncio.run(google_identity('code','verifier','test-nonce',self.settings))

    def test_real_verifier_rejects_wrong_audience_issuer_expiry_and_signature(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from google.auth import crypt, jwt
        from google.auth.exceptions import GoogleAuthError
        from google.oauth2.id_token import verify_oauth2_token
        private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        private_pem=private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        signer=crypt.RSASigner.from_string(private_pem,key_id='test-key')
        certificates={'test-key':private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()}
        def transport(*args,**kwargs): return SimpleNamespace(status=200,data=json.dumps(certificates).encode())
        now=int(time.time())
        claims={**self.claims,'iss':'https://accounts.google.com','aud':'test-client','iat':now,'exp':now+300}
        encoded=jwt.encode(signer,claims)
        self.assertEqual(verify_oauth2_token(encoded,transport,audience='test-client')['sub'],'stable-subject')
        near_future=jwt.encode(signer,{**claims,'iat':now+10})
        self.assertEqual(verify_oauth2_token(near_future,transport,audience='test-client',clock_skew_in_seconds=30)['sub'],'stable-subject')
        with self.assertRaises(ValueError):
            verify_oauth2_token(jwt.encode(signer,{**claims,'iat':now+90}),transport,audience='test-client',clock_skew_in_seconds=30)

        for overrides in [{'aud':'another-client'},{'iss':'https://attacker.test'},{'iat':now-600,'exp':now-300}]:
            with self.assertRaises((ValueError,GoogleAuthError)): verify_oauth2_token(jwt.encode(signer,{**claims,**overrides}),transport,audience='test-client')
        other_private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        other=crypt.RSASigner.from_string(other_private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()),key_id='test-key')
        with self.assertRaises(ValueError): verify_oauth2_token(jwt.encode(other,claims),transport,audience='test-client')

    def test_outstanding_login_flows_are_bounded(self):
        for _ in range(100): self.store.create_flow()
        async def check(client):
            result=await client.get('/api/auth/google/login')
            self.assertEqual(result.status_code,429)
        self.run_async(check)


    def test_callback_classifies_rejected_client_without_exposing_provider_details(self):
        state,browser,_,_=self.store.create_flow()
        response=httpx.Response(401,json={'error':'invalid_client','error_description':'sensitive-provider-detail'},request=httpx.Request('POST','https://oauth2.googleapis.com/token'))
        async def check(client):
            client.cookies.set(FLOW_COOKIE,browser)
            with patch('app.auth.httpx.AsyncClient.post',new=AsyncMock(return_value=response)),self.assertLogs('app.auth',level='WARNING') as logs:
                result=await client.get('/api/auth/google/callback',params={'state':state,'code':'private-code'})
            self.assertIn('auth_error=invalid_client',result.headers['location'])
            self.assertNotIn('sensitive-provider-detail',' '.join(logs.output)+result.text+result.headers['location'])
            self.assertNotIn('private-code',' '.join(logs.output)+result.headers['location'])
            self.assertIsNone((await client.get('/api/auth/session')).json()['user'])
        self.run_async(check)
