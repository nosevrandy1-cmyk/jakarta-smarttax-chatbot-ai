import unittest
from unittest.mock import patch
import test_dashboard_empty as fixtures
from app.ollama_service import build_retrieval_query
from app.embedder import embedder
import atexit
atexit.register(fixtures.knowledge_store.client.close)

class ContextualRetrievalTests(unittest.TestCase):
    def setUp(self):
        fixtures.EmptyDashboardTests.setUp(self)
        self.store=fixtures.knowledge_store

    def add(self,texts,name='Rujukan',tax='PBB-P2',pages=None,approve=True):
        metas=[{'source_type':'pdf_regulasi','doc_name':name,'domain':tax,'tema_pajak':tax,'chunk_index':i,'page_number':(pages or [1]*len(texts))[i]} for i in range(len(texts))]
        sid=self.store.archive.stage(texts,metas,None,'source.md')
        if approve:self.store.archive.review(sid,'approve','test','',self.store.collection,embedder)
        return sid

    def test_followup_search_keeps_user_topic_without_assistant_claims(self):
        history=[{'role':'user','content':'apa yang termasuk dalam pengertian bangunan'}, {'role':'assistant','content':'FAKTA YANG TIDAK BOLEH DISALIN'}]
        query=build_retrieval_query('detailnya apa aja',history)
        self.assertIn('pengertian bangunan',query)
        self.assertNotIn('FAKTA',query)
        self.assertEqual(build_retrieval_query('sebutkan NJOP Kalisari',history),'sebutkan NJOP Kalisari')
        self.assertEqual(build_retrieval_query('detailnya apa aja',[]),'detailnya apa aja')

    def test_text_search_is_tax_scoped_active_and_updated(self):
        sid=self.add(['Kalisari: nilai NJOP 3.100.000.'])
        self.add(['Kalisari reklame'],tax='REKLAME')
        self.add(['Kalisari belum aktif'],approve=False)
        ids=self.store.archive.search_text('sebutkan njop yang ada di kalisari','PBB-P2')
        self.assertEqual(len(ids),1)
        hits=self.store.query_knowledge('sebutkan njop yang ada di kalisari',tema_pajak='PBB-P2')
        self.assertTrue(any('3.100.000' in hit.text for hit in hits))
        self.store.archive.clear()
        self.assertEqual(self.store.archive.search_text('Kalisari','PBB-P2'),[])

    def test_intro_and_next_page_list_keep_separate_citations(self):
        self.add(['Termasuk dalam pengertian bangunan adalah :','a. jalan tol; b. kolam renang; c. pagar mewah.'],pages=[7,8])
        hits=self.store.query_knowledge('apa yang termasuk dalam pengertian bangunan',top_k=1,tema_pajak='PBB-P2')
        self.assertEqual([hit.metadata['page_number'] for hit in hits],[7,8])
        self.assertIn('kolam renang',hits[1].text)
        self.assertNotEqual(hits[0].chunk_id,hits[1].chunk_id)
