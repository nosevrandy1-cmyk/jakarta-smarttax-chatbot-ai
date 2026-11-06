import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import httpx
import test_dashboard_empty
import test_auth
from app.operations import OperationsStore,OperationsMiddleware,HardwareSampler,install_operations,classify

class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=OperationsStore(Path(self.temp.name)/'ops.sqlite')
    def tearDown(self):self.temp.cleanup()
    def test_retention_filters_and_aggregation(self):
        self.store.record('chat','Permintaan jawaban','POST',200,1200)
        self.store.record('auth','Google callback','GET',401,100)
        self.assertEqual(self.store.browse('auth')['total'],1)
        self.assertEqual(self.store.summary()['requests'],2)
        self.assertEqual(self.store.summary()['errors'],1)
        self.assertEqual(self.store.summary()['median_chat_ms'],1200)
        with self.store.connect() as db:db.execute('UPDATE events SET at=0')
        self.store.record('chat','Permintaan jawaban','POST',200,1)
        self.assertEqual(self.store.browse()['total'],1)
    def test_middleware_never_persists_secrets_and_times_full_stream(self):
        async def run():
            async def app(scope,receive,send):
                await send({'type':'http.response.start','status':200,'headers':[]})
                await send({'type':'http.response.body','body':b'PRIVATE ANSWER','more_body':False})
            async def receive():return {'type':'http.request','body':b'PRIVATE QUESTION'}
            async def send(message):pass
            middleware=OperationsMiddleware(app,self.store)
            await middleware({'type':'http','path':'/api/chat/stream','method':'POST','query_string':b'token=SECRET','headers':[(b'cookie',b'PRIVATE COOKIE')]},receive,send)
        asyncio.run(run());payload=json.dumps(self.store.browse())
        for secret in ['PRIVATE','SECRET','token','cookie']:self.assertNotIn(secret,payload)
        self.assertEqual(self.store.browse()['total'],1)
    def test_admin_routes_block_anonymous_and_ordinary_accounts(self):
        auth=test_auth.GoogleAuthTests();auth.setUp()
        queue=SimpleNamespace(_pending=0,max_waiting=4,_slots=SimpleNamespace(locked=lambda:False))
        install_operations(auth.app,SimpleNamespace(collection=SimpleNamespace(count=lambda:0)),queue,auth.settings,self.store)
        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=auth.app),base_url='http://localhost:8000') as client:
                for path in ['/api/admin/events','/api/admin/operations']:
                    self.assertEqual((await client.get(path)).status_code,401)
                token=auth.seed_session(auth.claims);client.cookies.set(auth.settings.session_cookie,token)
                for path in ['/api/admin/events','/api/admin/operations']:
                    self.assertEqual((await client.get(path)).status_code,403)
                token=auth.seed_session({**auth.claims,'sub':'developer','email':'developer@example.test','hd':'example.test'})
                client.cookies.set(auth.settings.session_cookie,token)
                res=await client.get('/api/admin/events');self.assertEqual(res.status_code,200)
                self.assertIn('no-store',res.headers['cache-control'])
                self.assertEqual((await client.get('/api/admin/events?limit=500')).status_code,422)
                self.assertEqual((await client.get('/api/admin/events?category=secret')).status_code,422)
        try:asyncio.run(run())
        finally:auth.tearDown()
    def test_missing_gpu_returns_unavailable_and_cached_sample(self):
        sampler=HardwareSampler()
        with patch('app.operations.shutil.which',return_value=None), patch('app.operations.DATA_DIR', Path(self.temp.name)):
            sample=sampler.sample();self.assertIsNone(sample['gpu']);self.assertIsNone(sample['cpu_temperature_c'])
            self.assertIs(sample,sampler.sample())

    def test_dashboard_summary_omits_evaluation_content(self):
        import ast
        from typing import Any,Dict
        from fastapi import FastAPI,Query
        from unittest.mock import AsyncMock
        node=next(n for n in ast.parse(Path('app/main.py').read_text(encoding='utf-8')).body if isinstance(n,ast.AsyncFunctionDef) and n.name=='get_rag_telemetry_endpoint')
        state={'latest_snapshot':{'items':[{'current_answer':'PRIVATE ANSWER'}],'ingested_source_meta':{'contributor':'PRIVATE PERSON'},'timestamp':'test'}}
        scope={'app':FastAPI(),'Query':Query,'Dict':Dict,'Any':Any,'eval_engine':SimpleNamespace(get_dashboard_state=AsyncMock(return_value=state))}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'app/main.py','exec'),scope)
        summary=asyncio.run(scope['get_rag_telemetry_endpoint'](False))
        self.assertNotIn('PRIVATE',json.dumps(summary))
        self.assertIn('PRIVATE',json.dumps(asyncio.run(scope['get_rag_telemetry_endpoint'](True))))

    def test_stream_error_and_backend_exception_are_diagnostic_without_payload(self):
        async def run(stream):
            async def app(scope,receive,send):
                if not stream:raise RuntimeError('SECRET TOKEN AND PRIVATE DOCUMENT')
                await send({'type':'http.response.start','status':200,'headers':[]})
                await send({'type':'http.response.body','body':b'{"type":"error","text":"PRIVATE ANSWER"}\n','more_body':False})
            async def receive():return {'type':'http.request','body':b''}
            async def send(message):pass
            middleware=OperationsMiddleware(app,self.store)
            await middleware({'type':'http','path':'/api/chat/stream','method':'POST'},receive,send)
        asyncio.run(run(True))
        with self.assertRaises(RuntimeError):asyncio.run(run(False))
        rows=self.store.browse(problems_only=True)['items']
        self.assertEqual(len(rows),2)
        self.assertEqual({r['error_code'] for r in rows},{'backend_exception','model_stream_error'})
        self.assertTrue(all(len(r['request_id'])==32 for r in rows))
        self.assertEqual(self.store.summary()['errors'],2)
        self.assertIsNone(self.store.summary()['median_chat_ms'])
        for secret in ['PRIVATE','SECRET','TOKEN']:self.assertNotIn(secret,json.dumps(rows))
