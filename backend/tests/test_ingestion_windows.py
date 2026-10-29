import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_dashboard_empty as fixtures
import pandas as pd
import pymupdf


class WindowsIngestionTests(unittest.TestCase):
    def setUp(self):
        self.store = fixtures.chroma_store
        self.assertEqual(fixtures.config.CHROMA_STORAGE_DIR, (fixtures.TEST_ROOT / 'chroma').resolve())
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), 'JST isolated PDF verification with readable text.')
        self.pdf = doc.tobytes()
        doc.close()

    def track_temporary_files(self, paths):
        original = tempfile.NamedTemporaryFile
        def create(*args, **kwargs):
            result = original(*args, **kwargs)
            paths.append(Path(result.name))
            return result
        return patch('app.rag_ingestion.tempfile.NamedTemporaryFile', side_effect=create)

    def test_pdf_extraction_releases_and_removes_temporary_file(self):
        paths = []
        with self.track_temporary_files(paths):
            summary = self.store.ingest_pdf(self.pdf, 'isolated-windows.pdf', 'PBB-P2', 'Test runner')
        self.assertGreater(summary['chunks_ingested'], 0)
        self.assertTrue(paths)
        self.assertTrue(all(not p.exists() for p in paths))

    def test_converter_error_still_closes_document_and_removes_file(self):
        paths = []
        documents = []
        def fail(document):
            documents.append(document)
            raise RuntimeError('conversion test error')
        with self.track_temporary_files(paths), patch('app.rag_ingestion.pymupdf4llm.to_markdown', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'conversion test error'):
                self.store.ingest_pdf(self.pdf, 'isolated-failure.pdf', 'PBB-P2', 'Test runner')
        self.assertTrue(documents[0].is_closed)
        self.assertTrue(paths)
        self.assertTrue(all(not p.exists() for p in paths))

    def test_xlsx_ingestion_with_windows_dependency_versions(self):
        output = io.BytesIO()
        pd.DataFrame([{'kategori': 'PBB-P2', 'keterangan': 'isolated worksheet verification'}]).to_excel(output, index=False)
        summary = self.store.ingest_excel(output.getvalue(), 'isolated-windows.xlsx', 'PBB-P2', 'Test runner')
        self.assertEqual(summary['rows_ingested'], 1)
        self.assertEqual(summary['sheets_processed'], 1)
