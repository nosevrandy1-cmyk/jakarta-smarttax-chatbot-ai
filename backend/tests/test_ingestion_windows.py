import io
import unittest
from unittest.mock import patch

import pandas as pd
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
import test_dashboard_empty as fixtures


def make_pdf(text=None, encrypted=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    if text:
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
            DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted:
        writer.encrypt('test-only-password')
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class WindowsIngestionTests(unittest.TestCase):
    def setUp(self):
        self.store = fixtures.chroma_store
        self.assertEqual(fixtures.config.CHROMA_STORAGE_DIR, (fixtures.TEST_ROOT / 'chroma').resolve())

    def test_pdf_text_reaches_collection_without_temporary_file(self):
        with patch('tempfile.NamedTemporaryFile', side_effect=AssertionError('Unexpected disk staging')):
            result = self.store.ingest_pdf(make_pdf('JST PDF readable reference'), 'compatibility.pdf')
        self.assertGreater(result['chunks_ingested'], 0)
        records = self.store.collection.get(where={'doc_name': 'compatibility.pdf'})
        self.assertTrue(any('JST PDF readable reference' in text for text in records['documents']))

    def assert_rejected_without_writes(self, data, message):
        with patch.object(self.store.collection, 'upsert') as upsert:
            with self.assertRaisesRegex(ValueError, message):
                self.store.ingest_pdf(data, 'invalid.pdf')
            upsert.assert_not_called()

    def test_malformed_pdf_has_readable_error_without_writes(self):
        self.assert_rejected_without_writes(b'%PDF-1.7\ninvalid', 'rusak|dibaca')

    def test_encrypted_pdf_is_rejected_without_writes(self):
        self.assert_rejected_without_writes(make_pdf('Private document', encrypted=True), 'terenkripsi')

    def test_image_only_or_blank_pdf_is_not_ingested(self):
        self.assert_rejected_without_writes(make_pdf(), 'Tidak ditemukan teks')

    def test_empty_upload_is_rejected(self):
        self.assert_rejected_without_writes(b'', 'kosong')

    def test_xlsx_ingestion_is_preserved(self):
        output = io.BytesIO()
        pd.DataFrame([{'kategori': 'PBB-P2', 'keterangan': 'isolated worksheet verification'}]).to_excel(output, index=False)
        result = self.store.ingest_excel(output.getvalue(), 'compatibility.xlsx', 'PBB-P2', 'Test runner')
        self.assertEqual(result['rows_ingested'], 1)
        self.assertEqual(result['sheets_processed'], 1)
