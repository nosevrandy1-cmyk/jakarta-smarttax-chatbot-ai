import json
import unittest
from unittest.mock import patch
import test_dashboard_empty
import test_room_memory as memory_fixtures
from app.room_memory import continuation_context, summarize_room, MAX_USER_MEMORY_BYTES


class CorrectionEvidenceTests(unittest.TestCase):
    setUp = memory_fixtures.RoomMemoryTests.setUp
    tearDown = memory_fixtures.RoomMemoryTests.tearDown

    def seed(self, long=False):
        uid=self.store.session(self.a)['id']
        def room(id,messages):return {'id':id,'title':'Test','theme':'PAT','updatedAt':1,'messages':messages}
        def user(text):return {'id':str(__import__('uuid').uuid4()),'role':'user','content':text}
        rooms=[room('a',[user('Kasus SUMUR-KENCANA-58: N1, 125 m3, resirkulasi aktif.')]),
               room('b',[user('Koreksi volume menjadi 150 m3. Parameter lain tetap.'),{'id':'assistant','role':'assistant','content':'AI_ONLY_POISON: volume kembali 125 m3.'},user('Apa volume terbaru?')]),room('c',[])]
        if long:rooms[0]['messages'].insert(0,user('x'*(MAX_USER_MEMORY_BYTES+1)))
        with self.store.connect() as db:
            self.store.history.save(uid,{'sessions':rooms,'activeSessionId':None},0,db)
            for child,parent in [('b','a'),('c','b')]:
                db.execute('INSERT INTO room_memories VALUES(?,?,?,?,?,?)',(uid,child,parent,'STALE_SUMMARY: pengguna kembali ke 125 m3.','old-version',1))
        return uid

    def test_original_correction_survives_wrong_assistant_and_old_summary(self):
        uid=self.seed()
        memory=continuation_context(self.store,uid,'c')
        parsed=json.loads(memory)
        statements=parsed['pernyataan_pengguna_urut_lama_ke_baru']
        self.assertIn('125 m3',statements[0])
        self.assertIn('150 m3',statements[1])
        self.assertEqual(statements[-1],'Apa volume terbaru?')
        self.assertNotIn('AI_ONLY_POISON',memory)
        self.assertNotIn('STALE_SUMMARY',memory)
        self.assertEqual(continuation_context(self.store,self.store.session(self.b)['id'],'c'),'')
        self.assertEqual(continuation_context(self.store,uid,'fresh'),'')

    def test_large_lineage_keeps_newest_correction_with_bounded_verbatim_context(self):
        uid=self.seed(long=True)
        data=json.loads(continuation_context(self.store,uid,'c'))
        self.assertLessEqual(sum(len(s.encode()) for s in data['pernyataan_pengguna_urut_lama_ke_baru']),MAX_USER_MEMORY_BYTES)
        self.assertTrue(any('150 m3' in s for s in data['pernyataan_pengguna_urut_lama_ke_baru']))
        self.assertIn('STALE_SUMMARY',data['ringkasan_lama_hanya_jika_tidak_bertentangan'])


class SummaryProvenanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_assistant_assertions_never_enter_summary_input(self):
        calls=[]
        class Response:
            def raise_for_status(self):pass
            def json(self):return {'message':{'content':'Pengguna mengoreksi volume menjadi 150 m3.'}}
        class Client:
            def __init__(self,*args,**kwargs):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def post(self,*args,**kwargs):calls.append(kwargs['json']);return Response()
        room={'messages':[{'role':'user','content':'Koreksi volume menjadi 150 m3.'},{'role':'assistant','content':'AI_ONLY_POISON: kembali 125 m3'}]}
        with patch('app.room_memory.httpx.AsyncClient',Client):await summarize_room(room,'')
        encoded=json.dumps(calls,ensure_ascii=False)
        self.assertNotIn('AI_ONLY_POISON',encoded)
        self.assertIn('150 m3',encoded)
