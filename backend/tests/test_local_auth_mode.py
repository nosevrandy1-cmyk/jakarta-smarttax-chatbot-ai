import asyncio
from dataclasses import replace
import unittest
import httpx
from fastapi import FastAPI, Request
import test_auth
from app.auth import install_auth
from app.chat_history import install_history


class LocalAuthModeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_auth.GoogleAuthTests();self.fixture.setUp()
        self.settings=replace(self.fixture.settings,enabled=False)
        self.app=self.build(self.settings)

    def tearDown(self):self.fixture.tearDown()

    def build(self,settings):
        app=FastAPI();install_auth(app,settings,self.fixture.store);install_history(app,self.fixture.store)
        @app.post('/api/chat')
        async def chat(request:Request):return {'developer':settings.is_developer(request.state.auth_user)}
        return app

    def test_local_session_and_mutation_still_require_csrf(self):
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='http://localhost:8000') as c:
                s=(await c.get('/api/auth/session')).json()
                self.assertFalse(s['auth_enabled']);self.assertTrue(s['user']['local'])
                self.assertEqual((await c.post('/api/chat')).status_code,403)
                headers={'Origin':self.settings.public_url,'X-CSRF-Token':s['csrf_token']}
                r=await c.post('/api/chat',headers=headers)
                self.assertEqual(r.json(),{'developer':True})
                headers['X-JST-Account-ID']=s['user']['id']
                r=await c.put('/api/history',headers=headers,json={'revision':0,'sessions':[],'activeSessionId':None})
                self.assertEqual(r.status_code,200)
                self.assertEqual((await c.get('/api/auth/google/login')).status_code,403)
        asyncio.run(check())

    def test_remote_requests_cannot_use_local_mode(self):
        async def check():
            transport=httpx.ASGITransport(app=self.app,client=('192.0.2.10',1234))
            async with httpx.AsyncClient(transport=transport,base_url='http://localhost:8000') as c:
                self.assertEqual((await c.get('/api/auth/session')).status_code,403)
        asyncio.run(check())

    def test_reenabling_auth_restores_login_requirement(self):
        app=self.build(replace(self.settings,enabled=True))
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost:8000') as c:
                self.assertEqual((await c.post('/api/chat')).status_code,401)
        asyncio.run(check())

    def test_public_configuration_cannot_enable_local_mode(self):
        with self.assertRaises(RuntimeError):self.build(replace(self.settings,public_url='https://example.test'))
