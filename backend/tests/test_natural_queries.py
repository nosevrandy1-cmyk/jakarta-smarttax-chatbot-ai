import unittest
import test_dashboard_empty as fixtures
from app.retrieval_text import normalize_legal_query, document_matches, legal_queries, passage_score
from app.ollama_service import build_retrieval_query

class NaturalQueryTests(unittest.TestCase):
    def test_short_document_identifiers_keep_identity(self):
        for query in ['Perda 16/2011','Perda No.16/2011','perda nomor 16/2011']:
            self.assertTrue(document_matches(query,'Perda Nomor 16 Tahun 2011'))
            self.assertFalse(document_matches(query,'Perda Nomor 16 Tahun 2024'))

    def test_comparison_infers_omitted_document_kind(self):
        parts=legal_queries('Beda Pergub 5/2023 sama 16/2024 apa?')
        self.assertEqual(len(parts),2)
        self.assertIn('pergub 5 tahun 2023',parts[0])
        self.assertIn('pergub 16 tahun 2024',parts[1])

    def test_natural_followups_retain_anchor(self):
        history=[{'role':'user','content':'Persentase NJOP hunian menurut Pergub 17/2024 berapa?'}]
        for question in ['Eh ralat, punya aku tanah kosong. Jadi berapa?', 'Jelasin dasar pasalnya dong','Tahun berapa yang kamu pakai?','Kolam renang termasuk juga?']:
            self.assertIn('Pergub 17 tahun 2024',build_retrieval_query(question,history))

    def test_negative_full_exemption_mention_is_not_eligibility(self):
        query='Siapa aja yang bisa bebas pokok PBB 100% menurut Pergub 16/2024?'
        title='Pergub Nomor 16 Tahun 2024'
        positive='Pembebasan pokok 100% diberikan untuk hunian dengan kriteria: a. nilai terbatas; b. orang pribadi dengan NIK.'
        negative='Syarat pengurangan pokok: a. SPPT nol rupiah; b. tidak memenuhi ketentuan pembebasan pokok 100%.'
        self.assertGreater(passage_score(query,positive,title),passage_score(query,negative,title))

    def test_context_does_not_override_new_explicit_rule(self):
        query=build_retrieval_query('Menurut Pergub 88/2025 apa syaratnya?', [{'role':'user','content':'Pergub 17/2024 persentasenya berapa?'}])
        self.assertNotIn('17 tahun 2024',query)
        self.assertIn('88 tahun 2025',query)

    def test_natural_exclusion_has_search_vocabulary(self):
        from app.retrieval_text import normalized_terms
        self.assertIn('pengecualian',normalized_terms('Objek apa aja yang nggak kena PBB?'))
