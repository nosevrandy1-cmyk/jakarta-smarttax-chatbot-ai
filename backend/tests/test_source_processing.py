import ast
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from app.markdown_import import ImportProgress
import io

class AllSourceProgressTests(IsolatedAsyncioTestCase):
    def scope(self):
        progress=ImportProgress()
        store=SimpleNamespace(ingest_pdf=Mock(return_value={'source_id':'test'}),ingest_excel=Mock(return_value={'source_id':'test'}),ingest_user_reasoning=Mock(return_value={'source_id':'test'}))
        scope=dict(app=FastAPI(),asynccontextmanager=asynccontextmanager,markdown_import_lock=asyncio.Lock(),import_progress=progress,
            HTTPException=HTTPException,Request=Request,UploadFile=UploadFile,File=File,Form=Form,Path=Path,Dict=Dict,Any=Any,
            LearnReasoningPayload=Any,MAX_UPLOAD_BYTES=20*1024*1024,knowledge_store=store,run_in_threadpool=run_in_threadpool,
            activate_uploaded_source=lambda summary,request:summary,eval_engine=SimpleNamespace(get_dashboard_state=AsyncMock(return_value={})))
        tree=ast.parse(Path('app/main.py').read_text(encoding='utf-8'))
        names={'source_processing','ingest_pdf_endpoint','ingest_excel_endpoint','learn_reasoning_endpoint'}
        nodes=[n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name in names]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'app/main.py','exec'),scope)
        return scope

    async def test_every_source_reports_completion_and_releases_shared_lock(self):
        s=self.scope();request=SimpleNamespace()
        calls=[('pdf',lambda:s['ingest_pdf_endpoint'](request,UploadFile(filename='a.pdf',file=io.BytesIO(b'%PDF test')))),
               ('table',lambda:s['ingest_excel_endpoint'](request,UploadFile(filename='a.csv',file=io.BytesIO(b'a,b\n1,2')))),
               ('case',lambda:s['learn_reasoning_endpoint'](SimpleNamespace(),request))]
        for kind,call in calls:
            result=await call()
            self.assertEqual(result['status'],'active')
            self.assertEqual(s['import_progress'].snapshot()['kind'],kind)
            self.assertEqual(s['import_progress'].snapshot()['phase'],'completed')
            self.assertFalse(s['markdown_import_lock'].locked())

    async def test_cross_type_overlap_is_rejected_before_work(self):
        s=self.scope()
        async with s['source_processing']('markdown'):
            with self.assertRaises(HTTPException) as error:
                await s['learn_reasoning_endpoint'](SimpleNamespace(),SimpleNamespace())
            self.assertEqual(error.exception.status_code,409)
            s['knowledge_store'].ingest_user_reasoning.assert_not_called()
            self.assertEqual(s['import_progress'].snapshot()['kind'],'markdown')

    async def test_parse_failure_reports_failure_and_unlocks(self):
        s=self.scope();s['knowledge_store'].ingest_pdf.side_effect=ValueError('invalid PDF')
        with self.assertRaises(HTTPException) as error:
            await s['ingest_pdf_endpoint'](SimpleNamespace(),UploadFile(filename='a.pdf',file=io.BytesIO(b'%PDF test')))
        self.assertEqual(error.exception.status_code,422)
        self.assertEqual(s['import_progress'].snapshot()['phase'],'failed')
        self.assertFalse(s['markdown_import_lock'].locked())

    async def test_work_does_not_block_event_loop(self):
        import threading
        s=self.scope();started=threading.Event();release=threading.Event()
        def slow(payload):
            started.set();release.wait(2);return {'source_id':'test'}
        s['knowledge_store'].ingest_user_reasoning.side_effect=slow
        task=asyncio.create_task(s['learn_reasoning_endpoint'](SimpleNamespace(),SimpleNamespace()))
        try:
            await asyncio.wait_for(asyncio.to_thread(started.wait,1),1.5)
            self.assertFalse(task.done())
            self.assertEqual(s['import_progress'].snapshot()['phase'],'checking')
        finally:release.set()
        await task
