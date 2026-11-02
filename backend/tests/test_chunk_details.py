import unittest
import test_dashboard_empty as fixtures
from app.rag_ingestion import chroma_store


class ChunkDetailTests(unittest.TestCase):
    def setUp(self):
        fixtures.EmptyDashboardTests.setUp(self)

    def test_empty_details_are_read_only(self):
        result=chroma_store.get_chunk_details()
        self.assertEqual(result['documents'],[])
        self.assertEqual(result['items'],[])
        self.assertEqual(result['total_documents'],0)
        self.assertEqual(chroma_store.collection.count(),0)

    def test_counts_search_pagination_and_metadata(self):
        from app.embedder import embedder
        for texts, metas in [(['Kalimat pertama','Google login untuk proyek'],
            [{'source_type':'pdf_regulasi','doc_name':'Dokumen.pdf','domain':'PBB-P2','chunk_index':0},
             {'source_type':'pdf_regulasi','doc_name':'Dokumen.pdf','domain':'PBB-P2','chunk_index':1}]),
            (['Dokumen kedua'],[{'source_type':'pdf_regulasi','doc_name':'Dokumen.pdf','domain':'PBB-P2','chunk_index':0,'page_number':2}])]:
            source_id = chroma_store.archive.stage(texts, metas, None, 'Dokumen.pdf')
            chroma_store.archive.review(source_id, 'approve', 'test', '', chroma_store.collection, embedder)
        result=chroma_store.get_chunk_details(limit=1)
        self.assertEqual(result['total_documents'],2)
        self.assertEqual(result['total_chunks'],3)
        self.assertEqual(sorted(d['chunk_count'] for d in result['documents']),[1,2])
        self.assertEqual(len(result['items']),1)
        self.assertEqual(chroma_store.get_collection_telemetry()['total_documents'],2)
        search=chroma_store.get_chunk_details(query='GOOGLE')
        self.assertEqual(search['matched_chunks'],1)
        self.assertIsNone(search['items'][0]['page'])
        filtered=chroma_store.get_chunk_details(source_id=search['items'][0]['source_id'],offset=1,limit=1)
        self.assertEqual(filtered['matched_chunks'],2)
        self.assertEqual(filtered['items'][0]['chunk_index'],1)
        self.assertEqual(chroma_store.get_chunk_details(query='absent')['items'],[])


if __name__=='__main__': unittest.main()
