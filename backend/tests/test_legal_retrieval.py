import unittest
import test_dashboard_empty as fixtures
from app.embedder import embedder
import atexit
atexit.register(fixtures.knowledge_store.client.close)
from app.retrieval_text import document_matches, passage_score

class LegalRetrievalTests(unittest.TestCase):
    def setUp(self):
        fixtures.EmptyDashboardTests.setUp(self)
        self.store = fixtures.knowledge_store

    def add(self, texts, title, tax='PBB-P2', approved=True):
        metas = [{'source_type':'pdf_regulasi','doc_name':title,'domain':tax,'tema_pajak':tax,'page_number':i+1,'chunk_index':i} for i in range(len(texts))]
        sid = self.store.archive.stage(texts, metas, None, 'source.md')
        if approved:
            self.store.archive.review(sid, 'approve', 'test', '', self.store.collection, embedder)
        return sid

    def test_percentage_paraphrases_find_substantive_article(self):
        title = 'Pergub Nomor 77 Tahun 2024 Tentang Persentase NJOP'
        self.add(['[SUMBER REGULASI: '+title+']\n# '+title,
                  '### Pasal 2\nHunian 37% dan selain Hunian 63% setelah dikurangi NJOPTKP.',
                  '### Pasal 3\nTanah kosong termasuk selain Hunian.'], title)
        self.add(['### Pasal 2\nHunian 99% dan selain Hunian 1%.'], 'Pergub Nomor 78 Tahun 2024')
        for ending in ['berapa?', 'berapa persen?', 'besarannya berapa?']:
            hits = self.store.query_knowledge('Menurut Pergub 77 tahun 2024 persentase NJOP hunian dan selain hunian '+ending, tema_pajak='PBB-P2')
            self.assertIn('37%', hits[0].text)
            self.assertTrue(all('78 Tahun' not in hit.doc_name for hit in hits))

    def test_article_expansion_includes_conditions_and_preserves_page(self):
        title = 'Pergub Nomor 88 Tahun 2024'
        self.add(['### Pasal 3\nPembebasan pokok 100% diberikan untuk satu objek.',
                  '### Pasal 3\nKriteria hunian dengan nilai paling banyak 900 juta dan NIK lengkap.',
                  '### Pasal 3\nJika lebih dari satu objek, pilih objek dengan nilai terbesar.',
                  '### Pasal 4\nPemutakhiran NIK tetap memenuhi kriteria Pasal 3 ayat (2).'], title)
        hits = self.store.query_knowledge('Menurut Pergub 88 tahun 2024 bagaimana pemutakhiran NIK?', tema_pajak='PBB-P2')
        self.assertTrue(any('900 juta' in hit.text for hit in hits))
        self.assertTrue(any('terbesar' in hit.text for hit in hits))
        pages = {hit.metadata['page_number'] for hit in hits}
        self.assertIn(2, pages)
        self.assertIn(3, pages)

    def test_expansion_does_not_leak_other_tax_or_unapproved_source(self):
        sid = self.add(['### Pasal 1\nKetentuan kriteria yang belum boleh dipublikasikan.'], 'Pergub Nomor 89 Tahun 2024', approved=False)
        import json
        cid = json.loads(self.store.archive.get(sid)['payload'])['ids'][0]
        self.assertEqual(self.store.archive.legal_context(cid, 'PBB-P2'), {})
        self.assertEqual(self.store.query_knowledge('Pergub 89 tahun 2024 kriteria', tema_pajak='PBB-P2'), [])

    def test_document_identity_and_heading_penalty(self):
        self.assertFalse(document_matches('Pergub 17 tahun 2024', 'Pergub Nomor 16 Tahun 2024'))
        self.assertLess(passage_score('persentase NJOP', '# Persentase NJOP', 'Rujukan'), 0)
        self.assertGreater(passage_score('persentase hunian', 'Hunian 37 persen.', 'Rujukan'), 0)

    def test_latest_followup_outweighs_old_condition_words(self):
        query = 'Apa syarat pembebasan 100% menurut Pergub 88 tahun 2024?\nPertanyaan terbaru: Kalau NIK belum lengkap?'
        target = '### Pasal 4\nJika NIK belum lengkap, ajukan pemutakhiran NIK sepanjang memenuhi kriteria Pasal 3.'
        other = '### Pasal 6\nKriteria pembebasan 100% untuk objek dengan kenaikan lebih dari 25%.'
        self.assertGreater(passage_score(query, target, 'Pergub Nomor 88 Tahun 2024'), passage_score(query, other, 'Pergub Nomor 88 Tahun 2024'))

    def test_dangling_internal_footer_is_not_saved_as_answer(self):
        from app.ollama_service import resolve_answer_references
        answer, refs = resolve_answer_references('Isi jawaban.\n\nmetadata\n', [])
        self.assertEqual(answer, 'Isi jawaban.')
        self.assertEqual(resolve_answer_references('Metadata sumber menyimpan halaman.', [])[0], 'Metadata sumber menyimpan halaman.')

    def test_exclusion_and_colloquial_eligibility_are_searchable(self):
        title = 'Pergub Nomor 88 Tahun 2024'
        self.add(['### Pasal 3\nPembebasan 100% diberikan dengan kriteria sebagai berikut: a. hunian; b. nilai paling banyak 900 juta.',
                  '### Pasal 4\nObjek yang tidak dikenakan PBB adalah a. kuburan; b. hutan lindung.'], title)
        for q, word in [('siapa yang bisa nggak bayar pokok PBB sama sekali', '900 juta'),
                        ('semua pengecualian objek PBB', 'kuburan')]:
            hits = self.store.query_knowledge('Pergub 88 tahun 2024 '+q, tema_pajak='PBB-P2')
            self.assertTrue(any(word in hit.text for hit in hits), q)

    def test_comparison_keeps_both_document_years(self):
        self.add(['### Pasal 2\nPembebasan 100% berlaku untuk nilai kurang dari 900 juta.'], 'Pergub Nomor 80 Tahun 2021')
        self.add(['### Pasal 3\nPembebasan 100% berlaku untuk nilai sampai dengan 900 juta.'], 'Pergub Nomor 81 Tahun 2022')
        hits = self.store.query_knowledge('Bandingkan batas pembebasan 100% Pergub 80 tahun 2021 dan Pergub 81 tahun 2022', tema_pajak='PBB-P2')
        self.assertTrue(any('80 Tahun 2021' in hit.doc_name for hit in hits))
        self.assertTrue(any('81 Tahun 2022' in hit.doc_name for hit in hits))
        self.assertTrue(any('kurang dari' in hit.text for hit in hits))
        self.assertTrue(any('sampai dengan' in hit.text for hit in hits))

    def test_correction_prefix_keeps_statute_context(self):
        from app.ollama_service import build_retrieval_query
        history = [{'role':'user','content':'Saya membahas persentase NJOP menurut Pergub 77 tahun 2024 untuk hunian.'}]
        for q in ['Ralat, objek saya tanah kosong. Persentasenya berapa?', 'Koreksi, objeknya tanah kosong.']:
            query = build_retrieval_query(q, history)
            self.assertIn('Pergub 77 tahun 2024', query)
            self.assertTrue(query.endswith(q))

    def test_model_subletter_references_resolve_only_existing_base(self):
        from app.ollama_service import resolve_answer_references
        candidate = {'number':9,'chunk_id':'actual-chunk'}
        text, refs = resolve_answer_references('Syarat [9a]. Syarat lain [9b]. Tidak ada [99a].', [candidate])
        self.assertEqual(text, 'Syarat [9]. Syarat lain [9]. Tidak ada .')
        self.assertEqual(refs, [candidate])
        text, refs = resolve_answer_references('Gabungan [9a, 9b, 99a].', [candidate])
        self.assertEqual(text, 'Gabungan [9].')
        self.assertEqual(refs, [candidate])
