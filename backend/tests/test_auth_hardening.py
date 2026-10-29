import asyncio
from dataclasses import replace
from pathlib import Path
import sqlite3
import time
import unittest
from unittest.mock import patch

import httpx
import test_auth as fixtures
from app.auth import AuthStore, SESSION_COOKIE, install_auth, validate_identity
from fastapi import FastAPI


class AuthHardeningTests(unittest.TestCase):
    setUp = fixtures.GoogleAuthTests.setUp
    tearDown = fixtures.GoogleAuthTests.tearDown
    run_async = fixtures.GoogleAuthTests.run_async

    def test_third_party_email_cannot_gain_developer_role(self):
        token=self.store.create_session({**self.claims,'email':'developer@example.test'})
        async def check(client):
            client.cookies.set(SESSION_COOKIE,token)
            self.assertEqual((await client.get('/api/auth/session')).json()['user']['role'],'user')
            self.assertEqual((await client.get('/api/rag/telemetry')).status_code,403)
        self.run_async(check)

    def test_email_allowlist_requires_google_authority(self):
        settings=replace(self.settings,allowed_emails=frozenset({'user@example.test'}))
        with self.assertRaises(PermissionError): validate_identity(self.claims,'test-nonce',settings)
        self.assertEqual(validate_identity({**self.claims,'hd':'example.test'},'test-nonce',settings)['sub'],'stable-subject')

    def test_changed_email_revokes_all_old_sessions(self):
        one=self.store.create_session(self.claims)
        two=self.store.create_session(self.claims)
        changed=self.store.create_session({**self.claims,'email':'changed@example.test'})
        self.assertIsNone(self.store.session(one))
        self.assertIsNone(self.store.session(two))
        self.assertIsNotNone(self.store.session(changed))

    def test_account_rate_limit_isolated_and_expires(self):
        one=self.store.create_session(self.claims)
        two=self.store.create_session({**self.claims,'sub':'second-user'})
        async def check(client):
            client.cookies.set(SESSION_COOKIE,one)
            csrf=(await client.get('/api/auth/session')).json()['csrf_token']
            headers={'Origin':self.settings.public_url,'X-CSRF-Token':csrf}
            for _ in range(10): self.assertEqual((await client.post('/api/chat/stream',headers=headers)).status_code,200)
            response=await client.post('/api/chat/stream',headers=headers)
            self.assertEqual(response.status_code,429)
            self.assertEqual(response.headers['retry-after'],'60')
            client.cookies.set(SESSION_COOKIE,two)
            headers['X-CSRF-Token']=(await client.get('/api/auth/session')).json()['csrf_token']
            self.assertEqual((await client.post('/api/chat/stream',headers=headers)).status_code,200)
        self.run_async(check)
        self.assertTrue(self.store.rate_limit('temporary-counter',1))
        self.assertFalse(self.store.rate_limit('temporary-counter',1))
        with patch('app.auth.time.time',return_value=time.time()+61):
            self.assertTrue(self.store.rate_limit('temporary-counter',1))

    def test_login_rate_limit_ignores_spoofed_forwarded_header(self):
        async def check(client):
            for i in range(20): self.assertEqual((await client.get('/api/auth/google/login',headers={'X-Forwarded-For':f'192.0.2.{i}'})).status_code,302)
            response=await client.get('/api/auth/google/login',headers={'X-Forwarded-For':'192.0.2.250'})
            self.assertEqual(response.status_code,429)
        self.run_async(check)

    def test_oversized_json_and_chunked_bodies_are_rejected(self):
        token=self.store.create_session(self.claims)
        async def chunks():
            yield b'x'*600000
            yield b'y'*600000
        async def check(client):
            client.cookies.set(SESSION_COOKIE,token)
            csrf=(await client.get('/api/auth/session')).json()['csrf_token']
            headers={'Origin':self.settings.public_url,'X-CSRF-Token':csrf,'Content-Type':'application/json'}
            self.assertEqual((await client.post('/api/chat/stream',headers=headers,content=b'x'*(1024*1024+1))).status_code,413)
            self.assertEqual((await client.post('/api/chat/stream',headers=headers,content=chunks())).status_code,413)
        self.run_async(check)

    def test_upload_envelope_is_bounded(self):
        token=self.store.create_session({**self.claims,'email':'developer@example.test','hd':'example.test'})
        async def check(client):
            client.cookies.set(SESSION_COOKIE,token)
            csrf=(await client.get('/api/auth/session')).json()['csrf_token']
            headers={'Origin':self.settings.public_url,'X-CSRF-Token':csrf,'Content-Length':str(22*1024*1024)}
            self.assertEqual((await client.post('/api/rag/ingest-pdf',headers=headers,content=b'x')).status_code,413)
        self.run_async(check)

    def test_production_login_cookie_uses_host_prefix(self):
        settings=replace(self.settings,public_url='https://jst.example.test',redirect_uri='https://jst.example.test/api/auth/google/callback')
        app=FastAPI()
        install_auth(app,settings,self.store)
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://jst.example.test') as client:
                response=await client.get('/api/auth/google/login')
                cookie=response.headers['set-cookie']
                self.assertIn('__Host-jst_google_flow=',cookie)
                self.assertIn('Secure',cookie);self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=lax',cookie)
                self.assertNotIn('Domain=',cookie)
        asyncio.run(check())

    def test_legacy_user_migration_preserves_data_and_denies_unproven_authority(self):
        path=Path(self.temp.name)/'legacy.sqlite'
        db=sqlite3.connect(path)
        db.execute('CREATE TABLE auth_users (id TEXT PRIMARY KEY, provider TEXT NOT NULL, subject TEXT NOT NULL,email TEXT NOT NULL,name TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,UNIQUE(provider,subject))')
        db.execute("INSERT INTO auth_users VALUES ('keep-id','google','old-sub','old@example.test','Old user',1,1)")
        db.execute('PRAGMA user_version=1');db.commit();db.close()
        migrated=AuthStore(path)
        migrated.initialize();migrated.initialize()
        with migrated.connect() as db:
            row=db.execute("SELECT * FROM auth_users WHERE id='keep-id'").fetchone()
            self.assertEqual(row['subject'],'old-sub')
            self.assertEqual(row['google_authoritative'],0)
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],2)

    def test_allowlist_revocation_and_developer_removal_apply_to_existing_sessions(self):
        token=self.store.create_session({**self.claims,'email':'developer@example.test','hd':'example.test'})
        settings=replace(self.settings,developer_emails=frozenset(),allowed_emails=frozenset({'another@example.test'}))
        app=FastAPI();install_auth(app,settings,self.store)
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8000') as client:
                client.cookies.set(SESSION_COOKIE,token)
                self.assertIsNone((await client.get('/api/auth/session')).json()['user'])
                self.assertEqual((await client.get('/api/rag/telemetry')).status_code,401)
        asyncio.run(check())

    def test_raw_chroma_routes_are_not_exposed_by_application(self):
        token=self.store.create_session({**self.claims,'email':'developer@example.test','hd':'example.test'})
        async def check(client):
            client.cookies.set(SESSION_COOKIE,token)
            self.assertEqual((await client.get('/api/v2/tenants/default_tenant/databases/default_database/collections')).status_code,404)
        self.run_async(check)


    def test_forbidden_responses_cannot_be_cached(self):
        token=self.store.create_session(self.claims)
        async def check(client):
            self.assertEqual((await client.get('/api/rag/telemetry')).headers['cache-control'],'no-store')
            client.cookies.set(SESSION_COOKIE,token)
            self.assertEqual((await client.get('/api/rag/telemetry')).headers['cache-control'],'no-store')
        self.run_async(check)

    def test_logout_still_works_after_general_api_rate_limit_is_reached(self):
        token=self.store.create_session(self.claims)
        session=self.store.session(token)
        for _ in range(120): self.store.rate_limit('api:'+session['id'],120)
        async def check(client):
            client.cookies.set(SESSION_COOKIE,token)
            response=await client.post('/api/auth/logout',headers={'Origin':self.settings.public_url,'X-CSRF-Token':session['csrf']})
            self.assertEqual(response.status_code,200)
            self.assertIsNone(self.store.session(token))
        self.run_async(check)
