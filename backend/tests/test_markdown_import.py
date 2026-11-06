import unittest
from app.markdown_import import parse_markdown, markdown_chunks, ImportProgress
from langchain_text_splitters import RecursiveCharacterTextSplitter

class MarkdownTests(unittest.TestCase):
    def test_package_pages_and_provenance(self):
        raw='---\nurl: "https://example.org/a"\ntitle: "Sumber A"\n---\n# A\n<!-- page: 2 | method: ocr -->\nIsi halaman kedua.\n---\n---\nurl: "https://example.org/b"\ntitle: "Sumber B"\n---\n# B\nIsi web.'
        docs=parse_markdown(raw.encode(),'package.md')
        self.assertEqual(len(docs),2)
        chunks=markdown_chunks(docs[0],RecursiveCharacterTextSplitter(chunk_size=100,chunk_overlap=10))
        self.assertTrue(any(p==2 and 'kedua' in t for p,h,t in chunks))
        self.assertEqual(docs[1]['url'],'https://example.org/b')
        self.assertTrue(all(p is None for p,t in docs[1]['segments']))
    def test_plain_markdown_and_bom(self):
        docs=parse_markdown(b'\xef\xbb\xbf# Judul\n\nIsi dokumen.','plain.md')
        self.assertEqual(docs[0]['title'],'Judul')
    def test_invalid_inputs(self):
        for raw in [b'',b'\xff',b'a\x00b', b'---\nurl: "file:///secret"\n---\nIsi', b'---\nurl: "https://u:p@example.org"\n---\nIsi',b'<!-- page: 0 -->\nIsi']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):parse_markdown(raw,'bad.md')
    def test_tables_preserved(self):
        raw='# Tarif\n\n| Kategori | Tarif |\n| --- | --- |\n| A | 2% |\n| B | 3% |'
        chunks=markdown_chunks(parse_markdown(raw.encode(),'table.md')[0],RecursiveCharacterTextSplitter(chunk_size=20,chunk_overlap=0))
        self.assertTrue(any('| A | 2% |' in t and '| Kategori | Tarif |' in t and '| B | 3% |' in t for p,h,t in chunks))
    def test_long_table_repeats_header_without_losing_rows(self):
        header = '| Kategori | Tarif |\n| --- | --- |'
        rows = [f'| Kategori {i} | {i}% |' for i in range(1500)]
        raw = '# Tarif\n\n' + header + '\n' + '\n'.join(rows)
        record = parse_markdown(raw.encode(), 'long.md')[0]
        record['segments'] = [(7, record['segments'][0][1])]
        chunks = markdown_chunks(record, RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=0))
        tables = [t for _, _, t in chunks if '| Kategori | Tarif |' in t]
        self.assertGreater(len(tables), 1)
        self.assertTrue(all(t.startswith(header) for t in tables))
        actual = [row for t in tables for row in t.splitlines()[2:]]
        self.assertEqual(actual, rows)
        self.assertTrue(all(page == 7 for page, _, _ in chunks))

    def test_single_oversized_row_stays_intact(self):
        row = '| A | ' + 'x' * 15000 + ' |'
        raw = '| Kategori | Isi |\n| --- | --- |\n' + row
        chunks = markdown_chunks(parse_markdown(raw.encode(), 'wide.md')[0], RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=0))
        self.assertEqual(len(chunks), 1)
        self.assertIn(row, chunks[0][2])

    def test_package_limit(self):
        raw=('---\nurl: "https://example.org"\n---\nIsi\n'*101).encode()
        with self.assertRaises(ValueError):parse_markdown(raw,'bad.md')

if __name__=='__main__':unittest.main()


class MarkdownIntakeTests(unittest.IsolatedAsyncioTestCase):
    async def test_preview_import_repeat_and_failure(self):
        import ast, asyncio, io
        from pathlib import Path
        from types import SimpleNamespace
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock, patch
        from fastapi import FastAPI, File, Form, Request, UploadFile, HTTPException
        from fastapi.concurrency import run_in_threadpool
        import test_dashboard_empty as fixtures
        from app.embedder import embedder
        store=fixtures.knowledge_store
        # The test environment redirects every storage path to a temporary directory.
        store.archive.clear()
        ids=store.collection.get()['ids']
        if ids:store.collection.delete(ids=ids)
        tree=ast.parse(Path('app/main.py').read_text(encoding='utf-8'))
        fn=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='ingest_markdown_endpoint')
        scope=dict(app=FastAPI(),asyncio=asyncio,Path=Path,Request=Request,File=File,Form=Form,
                   UploadFile=UploadFile,HTTPException=HTTPException,run_in_threadpool=run_in_threadpool,
                   parse_markdown=parse_markdown,markdown_chunks=markdown_chunks,import_progress=ImportProgress(),
                   markdown_import_lock=asyncio.Lock(),knowledge_store=store,embedder=embedder,
                   MAX_UPLOAD_BYTES=20*1024*1024,datetime=datetime,timezone=timezone,
                   eval_engine=SimpleNamespace(get_dashboard_state=AsyncMock(return_value={})))
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'app/main.py','exec'),scope)
        endpoint=scope['ingest_markdown_endpoint']
        request=SimpleNamespace(state=SimpleNamespace(auth_user={'id':'developer-test'}))
        raw=b'---\nurl: "https://example.org/rule"\ntitle: "Regulasi Uji"\n---\n<!-- page: 3 | method: text-layer -->\n# Ketentuan\n\nInformasi unik pengujian impor Markdown.'
        def upload():return UploadFile(filename='package.md',file=io.BytesIO(raw))
        before=store.collection.count()
        preview=await endpoint(request,upload(),'PBB-P2','Test',True)
        self.assertEqual(preview['source_count'],1)
        self.assertEqual(scope['import_progress'].snapshot()['phase'], 'ready')
        self.assertEqual(store.collection.count(),before)
        self.assertEqual(store.archive.list(),[])
        imported=await endpoint(request,upload(),'PBB-P2','Test',False)
        self.assertEqual(imported['sources'][0]['status'],'active')
        self.assertEqual(scope['import_progress'].snapshot()['phase'], 'completed')
        self.assertEqual(scope['import_progress'].snapshot()['completed'], 1)
        source=imported['sources'][0]['source_id']
        detail=store.archive.detail(source)
        self.assertTrue(all(c['page']==3 for c in detail['chunks']))
        self.assertEqual(detail['source_url'],'https://example.org/rule')
        original,_=store.archive.file(source)
        self.assertEqual(parse_markdown(original.read_bytes(),'source.md')[0]['url'],'https://example.org/rule')
        count=store.collection.count()
        repeated=await endpoint(request,upload(),'PBB-P2','Test',False)
        self.assertEqual(repeated['sources'][0]['status'],'skipped')
        self.assertEqual(store.collection.count(),count)
        await scope['markdown_import_lock'].acquire()
        try:
            with self.assertRaises(HTTPException) as error:
                await endpoint(request,upload(),'PBB-P2','Test',False)
            self.assertEqual(error.exception.status_code,409)
        finally:scope['markdown_import_lock'].release()
        with patch.object(store.archive,'activate',side_effect=RuntimeError('test failure')):
            failed=await endpoint(request,upload(),'PAT','Test',False)
        self.assertEqual(failed['sources'][0]['status'],'failed')
