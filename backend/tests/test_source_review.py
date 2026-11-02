import asyncio
import io
import json
import unittest
from unittest.mock import patch
import httpx
from pypdf import PdfWriter
import test_dashboard_empty as fixtures
from test_ingestion_windows import make_pdf
import test_auth
from app.embedder import embedder
from app.rag_ingestion import LearnReasoningPayload
from app.source_routes import install_source_routes


class SourceReviewTests(unittest.TestCase):
    def setUp(self):
        fixtures.EmptyDashboardTests.setUp(self)
        self.store = fixtures.chroma_store

    def stage(self):
        return self.store.ingest_pdf(make_pdf('SOURCE UNIQUE TEST'), '../../original.pdf')

    def approve(self, result):
        return self.store.archive.review(result['source_id'], 'approve', 'test-developer', 'Checked', self.store.collection, embedder)

    def test_original_bytes_preserved_and_pending_not_searchable(self):
        result = self.stage()
        path, _ = self.store.archive.file(result['source_id'])
        self.assertEqual(path.read_bytes(), make_pdf('SOURCE UNIQUE TEST'))
        self.assertEqual(path.parent.resolve(), fixtures.config.UPLOAD_STAGING_DIR.resolve())
        self.assertNotIn('original', path.name)
        self.assertEqual(self.store.collection.count(), 0)
        self.assertEqual(self.store.query_knowledge('SOURCE UNIQUE TEST'), [])
        self.assertEqual(self.store.get_collection_telemetry()['total_chunks'], 0)

    def test_approval_activates_pages_and_audits_reviewer(self):
        result = self.stage()
        self.approve(result)
        hits = self.store.query_knowledge('SOURCE UNIQUE TEST')
        self.assertTrue(hits)
        self.assertEqual(hits[0].metadata['page_number'], 1)
        self.assertEqual(len(hits[0].metadata['content_sha256']), 64)
        row = self.store.archive.get(result['source_id'])
        self.assertEqual(row['reviewed_by'], 'test-developer')
        self.assertTrue(row['reviewed_at'])
        with self.assertRaises(ValueError): self.approve(result)

    def test_rejected_source_never_activates(self):
        result = self.stage()
        with self.assertRaises(ValueError):
            self.store.archive.review(result['source_id'], 'reject', 'test', '', self.store.collection, embedder)
        self.store.archive.review(result['source_id'], 'reject', 'test', 'Wrong document', self.store.collection, embedder)
        self.assertEqual(self.store.query_knowledge('SOURCE UNIQUE TEST'), [])
        with self.assertRaises(ValueError): self.approve(result)

    def test_physical_pages_and_blank_page_warning(self):
        writer = PdfWriter()
        from pypdf import PdfReader
        for text in ['PAGE ONE', None, 'PAGE THREE']:
            writer.add_page(PdfReader(io.BytesIO(make_pdf(text))).pages[0])
        stream = io.BytesIO(); writer.write(stream)
        result = self.store.ingest_pdf(stream.getvalue(), 'multipage.pdf')
        detail = self.store.archive.detail(result['source_id'])
        self.assertEqual([c['page'] for c in detail['chunks']], [1, 3])
        self.assertEqual(detail['page_count'], 3)
        self.assertTrue(any('Halaman 2' in w for w in detail['warnings']))

    def test_interrupted_index_write_is_not_visible(self):
        result = self.stage()
        row = self.store.archive.get(result['source_id'])
        payload = json.loads(row['payload'])
        self.store.collection.upsert(**payload, embeddings=embedder.embed_texts(payload['documents']))
        self.assertGreater(self.store.collection.count(), 0)
        self.assertEqual(self.store.query_knowledge('SOURCE UNIQUE TEST'), [])
        self.assertEqual(self.store.get_chunk_details()['total_chunks'], 0)

    def test_failed_approval_stays_pending(self):
        result = self.stage()
        with patch.object(self.store.collection, 'upsert', side_effect=RuntimeError('test failure')):
            with self.assertRaises(RuntimeError): self.approve(result)
        self.assertEqual(self.store.archive.get(result['source_id'])['status'], 'pending')
        self.assertEqual(self.store.collection.count(), 0)

    def test_same_name_same_size_different_content_has_different_identity(self):
        a=self.store.ingest_pdf(make_pdf('AAAA'), 'same.pdf')
        b=self.store.ingest_pdf(make_pdf('BBBB'), 'same.pdf')
        self.assertNotEqual(a['source_id'],b['source_id'])
        self.assertNotEqual(self.store.archive.detail(a['source_id'])['content_sha256'], self.store.archive.detail(b['source_id'])['content_sha256'])

    def test_table_and_case_also_wait_for_approval(self):
        table=self.store.ingest_excel(b'name,value\nTEST,42\n','test.csv')
        case=self.store.ingest_user_reasoning(LearnReasoningPayload(pertanyaan_kasus='Pertanyaan pengujian kasus',alur_penalaran='Penjelasan pengujian alur kasus',jawaban_final='Jawaban akhir pengujian',topik_pajak='PBB-P2',kontributor='Test runner'))
        self.assertEqual(table['review_status'],'pending')
        self.assertEqual(case['review_status'],'pending')
        self.assertEqual(self.store.collection.count(),0)
        with self.assertRaises(KeyError): self.store.archive.file('../auth.sqlite')

    def test_routes_enforce_developer_and_csrf(self):
        auth=test_auth.GoogleAuthTests(); auth.setUp()
        install_source_routes(auth.app,self.store,embedder)
        source=self.stage()['source_id']
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=auth.app),base_url='http://localhost:8000') as client:
                self.assertEqual((await client.get('/api/rag/sources')).status_code,401)
                token=auth.seed_session(auth.claims)
                client.cookies.set(auth.settings.session_cookie,token)
                for path in ['/api/rag/sources',f'/api/rag/sources/{source}',f'/api/rag/sources/{source}/file']:
                    self.assertEqual((await client.get(path)).status_code,403)
                token=auth.seed_session({**auth.claims,'sub':'developer','email':'developer@example.test','hd':'example.test'})
                client.cookies.set(auth.settings.session_cookie,token)
                self.assertEqual((await client.get(f'/api/rag/sources/{source}/file')).status_code,200)
                self.assertEqual((await client.post(f'/api/rag/sources/{source}/process')).status_code,403)
                response=await client.post(f'/api/rag/sources/{source}/process',headers={'Origin':auth.settings.public_url,'X-CSRF-Token':auth.store.session(token)['csrf']})
                self.assertEqual(response.status_code,200,response.text)
        try: asyncio.run(check())
        finally: auth.tearDown()
