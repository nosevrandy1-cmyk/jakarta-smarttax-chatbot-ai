import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_dashboard_empty
from test_chat_grounding import Model, Reply
from app import ollama_service as chat


class AnswerReferenceTests(unittest.IsolatedAsyncioTestCase):
    def test_uncited_retrieved_source_is_not_a_reference(self):
        answer,refs=chat.resolve_answer_references('Halo, ada yang ingin ditanyakan?', [{'number':1}])
        self.assertEqual(refs,[])
        self.assertIn('Halo',answer)

    def test_unknown_markers_are_removed_and_duplicates_are_not_repeated(self):
        answer,refs=chat.resolve_answer_references('Pertama [2]. Lalu [1]. Lagi [2]. Tidak valid [99].',
            [{'number':1,'document_name':'Satu.pdf'},{'number':2,'document_name':'Dua.pdf'}])
        self.assertEqual([ref['document_name'] for ref in refs],['Dua.pdf','Satu.pdf'])
        self.assertNotIn('[99]',answer)

    def test_no_document_cannot_produce_a_reference(self):
        answer,refs=chat.resolve_answer_references('Klaim [1].',[])
        self.assertEqual(refs,[])
        self.assertNotIn('[1]',answer)

    async def test_stream_and_json_response_resolve_same_real_source(self):
        hit=SimpleNamespace(doc_name='PRD.pdf',text='Login menggunakan Google.',chunk_id='pdf-test-0001',
            source_type='pdf_regulasi',metadata={'chunk_index':1},model_dump=lambda:{'doc_name':'PRD.pdf'})
        store=SimpleNamespace(query_knowledge=lambda *a,**k:[hit],get_collection_telemetry=lambda:
            {'total_chunks':1,'recent_sources':[{'doc_name':'PRD.pdf','source_type':'pdf_regulasi','domain':'PBB-P2'}]})
        def respond(*args,**kwargs):return Reply('Login direncanakan memakai Google [1]. Tidak sah [8].')
        with patch.object(chat,'chroma_store',store),patch.object(chat.httpx,'AsyncClient',Model),patch.object(Model,'stream',respond):
            result=await chat.run_smarttax_chat('Bagaimana login?',[])
        self.assertNotIn('[8]',result['answer'])
        self.assertEqual(len(result['references']),1)
        source=result['references'][0]
        self.assertEqual(source['document_name'],'PRD.pdf')
        self.assertEqual(source['chunk_id'],'pdf-test-0001')
        self.assertEqual(source['chunk_index'],1)
        self.assertIsNone(source['page'])


if __name__=='__main__':unittest.main()
