import tempfile
from pathlib import Path
import unittest
from app.vector_store import QdrantRecords


class QdrantRecordsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='jst-qdrant-unit-')
        self.records=QdrantRecords(Path(self.temp.name)/'index','','unit_sources',3)

    def tearDown(self):
        self.records.client.close()
        self.temp.cleanup()

    def put(self):
        self.records.upsert(ids=['pdf-a-0','pdf-b-0'],embeddings=[[1.,0.,0.],[0.,1.,0.]],
            documents=['Dokumen A','Dokumen B'],metadatas=[{'document_id':'a','domain':'PBB-P2','page_number':2},
                                                       {'document_id':'b','domain':'PBJT','page_number':3}])

    def test_upsert_get_query_and_delete_preserve_ids_text_and_pages(self):
        self.put()
        self.assertEqual(self.records.count(),2)
        result=self.records.query([[1.,0.,0.]],2,where={'document_id':{'$in':['a']}})
        self.assertEqual(result['ids'],[['pdf-a-0']])
        self.assertEqual(result['metadatas'][0][0]['page_number'],2)
        self.assertAlmostEqual(result['distances'][0][0],0.,places=5)
        self.assertEqual(self.records.get(ids=['pdf-b-0'])['documents'],['Dokumen B'])
        self.records.delete(['pdf-a-0'])
        self.assertEqual(self.records.count(),1)

    def test_filters_never_fall_back_to_unrelated_domain(self):
        self.put()
        result=self.records.query([[1.,0.,0.]],2,where={'$and':[{'document_id':{'$in':['a']}},{'domain':'PBJT'}]})
        self.assertEqual(result['ids'],[[]])
        with self.assertRaises(ValueError):self.records.get(where={'domain':{'$unknown':'PBJT'}})

    def test_reimport_updates_same_chunk_without_duplicates(self):
        self.put();self.put()
        self.assertEqual(self.records.count(),2)
        self.assertEqual(len(self.records.get(include=['embeddings'])['embeddings']),2)

    def test_scroll_reads_more_than_one_page(self):
        self.records.upsert(ids=[f'chunk-{i}' for i in range(270)],embeddings=[[1.,0.,0.]]*270,
            documents=['text']*270,metadatas=[{'document_id':'a'}]*270)
        self.assertEqual(len(self.records.get()['ids']),270)

    def test_invalid_dimensions_do_not_write(self):
        with self.assertRaises(ValueError):
            self.records.upsert(ids=['bad'],embeddings=[[1.,0.]],documents=['bad'],metadatas=[{}])
        self.assertEqual(self.records.count(),0)


    def test_embedded_data_survives_process_restart(self):
        import subprocess, sys
        path=str(Path(self.temp.name)/'restart-index')
        writer="from app.vector_store import QdrantRecords; import sys; r=QdrantRecords(sys.argv[1],'','restart',3); r.upsert(ids=['original-id'],embeddings=[[1.,0.,0.]],documents=['persistent source'],metadatas=[{'page_number':7}]);r.client.close()"
        reader="from app.vector_store import QdrantRecords; import sys,json; r=QdrantRecords(sys.argv[1],'','restart',3);print(json.dumps(r.get()));r.client.close()"
        subprocess.check_call([sys.executable,'-c',writer,path])
        import json
        result=json.loads(subprocess.check_output([sys.executable,'-c',reader,path],text=True))
        self.assertEqual(result['ids'],['original-id'])
        self.assertEqual(result['metadatas'][0]['page_number'],7)
