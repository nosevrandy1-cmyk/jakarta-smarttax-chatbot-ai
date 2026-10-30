import unittest
from unittest.mock import patch
import test_dashboard_empty as fixtures
from test_ingestion_windows import make_pdf
from app.embedder import embedder


class AutomaticSourceTests(unittest.TestCase):
    def setUp(self):
        fixtures.EmptyDashboardTests.setUp(self)
        self.store=fixtures.chroma_store

    def test_success_is_active_and_records_uploader(self):
        result=self.store.ingest_pdf(make_pdf('AUTO TRUSTED SOURCE'), 'automatic.pdf')
        detail=self.store.archive.activate(result['source_id'],'developer-test-id',self.store.collection,embedder)
        self.assertEqual(detail['status'],'approved')
        self.assertEqual(detail['uploaded_by'],'developer-test-id')
        self.assertEqual(detail['activation_mode'],'automatic')
        self.assertTrue(self.store.query_knowledge('AUTO TRUSTED SOURCE'))

    def test_embedding_failure_remains_inactive_and_can_be_retried(self):
        result=self.store.ingest_pdf(make_pdf('AUTO RETRY SOURCE'), 'retry.pdf')
        with patch.object(embedder,'embed_texts',side_effect=RuntimeError('test only')):
            with self.assertRaises(RuntimeError):
                self.store.archive.activate(result['source_id'],'uploader-id',self.store.collection,embedder)
        self.assertEqual(self.store.archive.detail(result['source_id'])['status'],'failed')
        self.assertEqual(self.store.query_knowledge('AUTO RETRY SOURCE'),[])
        detail=self.store.archive.activate(result['source_id'],'different-retrying-developer',self.store.collection,embedder)
        self.assertEqual(detail['uploaded_by'],'uploader-id')
        self.assertEqual(detail['status'],'approved')

    def test_incomplete_extraction_does_not_auto_activate(self):
        source_id=self.store.archive.stage(['Partial text'],[{'doc_name':'scan.pdf','source_type':'pdf_regulasi'}],
            b'%PDF-test-only','scan.pdf',['Halaman 2 tidak memiliki teks.'])
        with self.assertRaisesRegex(ValueError,'OCR'):
            self.store.archive.activate(source_id,'developer',self.store.collection,embedder)
        self.assertEqual(self.store.archive.detail(source_id)['status'],'failed')
        self.assertEqual(self.store.collection.count(),0)

    def test_old_pending_source_can_process_without_manual_approval(self):
        result=self.store.ingest_excel(b'item,value\nAUTOMATIC,42\n','trusted.csv')
        detail=self.store.archive.activate(result['source_id'],'developer',self.store.collection,embedder)
        self.assertEqual(detail['status'],'approved')
        with self.assertRaises(ValueError):
            self.store.archive.activate(result['source_id'],'developer',self.store.collection,embedder)
