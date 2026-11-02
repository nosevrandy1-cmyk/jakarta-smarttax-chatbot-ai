import sqlite3
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import test_auth as fixtures
from app.auth import FLOW_COOKIE, SESSION_COOKIE, GoogleLoginError, AuthStore


class RegistrationTests(unittest.TestCase):
    setUp = fixtures.GoogleAuthTests.setUp
    tearDown = fixtures.GoogleAuthTests.tearDown
    run_async = fixtures.GoogleAuthTests.run_async

    def test_registration_requests_consent_while_login_only_selects_account(self):
        async def check(client):
            for intent, expected in [('register', 'select_account consent'), ('login', 'select_account')]:
                response = await client.get('/api/auth/google/' + intent)
                self.assertEqual(response.status_code, 302)
                query = parse_qs(urlparse(response.headers['location']).query)
                self.assertEqual(query['prompt'], [expected])
                self.assertEqual(query['scope'], ['openid email profile'])
                self.assertEqual(query['redirect_uri'], [self.settings.redirect_uri])
        self.run_async(check)

    def counts(self):
        with self.store.connect() as db:
            return tuple(db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                         for table in ['auth_users', 'auth_sessions'])

    def callback(self, intent, extra=None):
        async def check(client):
            start = await client.get('/api/auth/google/' + intent)
            self.assertEqual(start.status_code, 302)
            state = parse_qs(urlparse(start.headers['location']).query)['state'][0]
            with patch('app.auth.google_identity', new=AsyncMock(return_value=self.claims)):
                self.response = await client.get('/api/auth/google/callback',
                    params={'state': state, 'code': 'test-code', **(extra or {})})
            self.session = (await client.get('/api/auth/session')).json()
        self.run_async(check)
        return self.response

    def test_login_unknown_account_never_registers_or_issues_session(self):
        response = self.callback('login')
        self.assertIn('auth_error=not_registered', response.headers['location'])
        self.assertIsNone(self.session['user'])
        self.assertNotIn(SESSION_COOKIE + '=', response.headers.get('set-cookie', ''))
        self.assertEqual(self.counts(), (0, 0))

    def test_registration_creates_user_and_session_then_existing_login_works(self):
        self.assertEqual(self.callback('register').headers['location'], self.settings.public_url + '/')
        first_id = self.session['user']['id']
        self.assertEqual(self.session['user']['role'], 'user')
        self.assertEqual(self.counts(), (1, 1))
        self.callback('login')
        self.assertEqual(self.session['user']['id'], first_id)
        self.assertEqual(self.counts(), (1, 2))

    def test_duplicate_registration_changes_nothing_and_issues_no_session(self):
        self.store.create_session(self.claims, intent='register')
        before = self.counts()
        self.claims = {**self.claims, 'name': 'Must not overwrite existing profile'}
        response = self.callback('register')
        self.assertIn('auth_error=already_registered', response.headers['location'])
        self.assertIsNone(self.session['user'])
        self.assertEqual(self.counts(), before)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT name FROM auth_users').fetchone()[0], 'Test User')

    def test_callback_query_cannot_turn_login_into_registration(self):
        response = self.callback('login', {'intent': 'register', 'register': 'true'})
        self.assertIn('auth_error=not_registered', response.headers['location'])
        self.assertEqual(self.counts(), (0, 0))

    def test_google_subject_not_shared_email_controls_registration(self):
        self.store.create_session(self.claims, intent='register')
        self.claims = {**self.claims, 'sub': 'different-google-subject'}
        self.assertIn('not_registered', self.callback('login').headers['location'])
        self.assertEqual(self.counts(), (1, 1))

    def test_store_default_login_fails_closed_and_rejects_invalid_intent(self):
        with self.assertRaises(GoogleLoginError):
            self.store.create_session(self.claims)
        with self.assertRaises(ValueError):
            self.store.create_session(self.claims, intent='automatic')
        with self.assertRaises(ValueError):
            self.store.create_flow('automatic')
        self.assertEqual(self.counts(), (0, 0))

    def test_registration_requires_state_and_browser_binding(self):
        state, _, _, _ = self.store.create_flow('register')
        async def check(client):
            with patch('app.auth.google_identity', new=AsyncMock()) as exchange:
                result = await client.get('/api/auth/google/callback', params={'state':state, 'code':'code'})
                self.assertIn('invalid_state', result.headers['location'])
                exchange.assert_not_called()
        self.run_async(check)
        self.assertEqual(self.counts(), (0, 0))

    def test_v2_migration_preserves_existing_users_sessions_and_flows_default_login(self):
        path = self.settings.database.parent / 'legacy-v2.sqlite'
        store = AuthStore(path)
        store.initialize()
        token = store.create_session(self.claims, intent='register')
        old_id = store.session(token)['id']
        state, browser, _, _ = store.create_flow()
        db = sqlite3.connect(path)
        try:
            with db:
                db.execute('ALTER TABLE auth_flows DROP COLUMN intent')
                db.execute('PRAGMA user_version=2')
        finally:
            db.close()
        store.initialize()
        self.assertEqual(store.session(token)['id'], old_id)
        self.assertEqual(store.consume_flow(state, browser)['intent'], 'login')
        with store.connect() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 3)
