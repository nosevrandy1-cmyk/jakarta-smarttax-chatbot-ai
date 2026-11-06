import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_dashboard_empty
from app.room_context import resolve_room_history
from app.ollama_service import build_chat_messages,build_retrieval_query
from app.source_review import text_query_scope
from app.chat_models import ChatRequestInput

class RoomContextTests(unittest.TestCase):
    def test_loaded_tail_preserves_room_beginning(self):
        stored=[{'id':str(i),'role':'user' if i%2==0 else 'assistant','content':f'message {i}'} for i in range(40)]
        result=resolve_room_history(stored[-6:],{'messages':stored},'next')
        self.assertEqual(len(result),40)
        self.assertEqual(result[0]['content'],'message 0')

    def test_edited_tail_replaces_stale_future(self):
        stored=[{'id':'a','role':'user','content':'Kalisari 2018'}, {'id':'b','role':'assistant','content':'old answer'}, {'id':'c','role':'user','content':'old future'}]
        tail=[{'id':'b','role':'assistant','content':'corrected answer'}]
        self.assertEqual([m['content'] for m in resolve_room_history(tail,{'messages':stored},'next')],['Kalisari 2018','corrected answer'])

    def test_new_room_is_empty_and_autosaved_current_turn_is_not_duplicated(self):
        self.assertEqual(resolve_room_history([],None,'halo'),[])
        self.assertEqual(resolve_room_history([],{'messages':[{'role':'user','content':'halo'}]},'halo'),[])

    def test_owner_scoping_applies_to_restored_history(self):
        from app import main
        owner_calls=[]
        def room(owner,room_id):
            owner_calls.append((owner,room_id))
            return {'messages':[{'id':'old','role':'user','content':'Objek MELATI'}]} if (owner,room_id)==('A','room-A') else None
        request=SimpleNamespace(state=SimpleNamespace(auth_user={'id':'A'}))
        with patch.object(main,'_auth_store',SimpleNamespace(history=SimpleNamespace(room=room))):
            self.assertIn('MELATI',str(main.check_room_context(ChatRequestInput(message='objeknya apa',room_id='room-A'),request)))
            self.assertEqual(main.check_room_context(ChatRequestInput(message='objeknya apa',room_id='room-B'),request),[])
        self.assertEqual(owner_calls,[('A','room-A'),('A','room-B')])

    def test_short_chain_keeps_street_year_code_and_classes(self):
        history=[]
        for question in ['Berapa NJOP Jalan Kalisari tahun 2018?','Yang kode 003 aja.','Kelas AE dan AR berapa?','Rata-rata keduanya berapa?','Kalau selisih?']:
            query=build_retrieval_query(question,history)
            if history:
                self.assertIn('Kalisari',query)
                self.assertIn('2018',query)
            if len(history)>=4:
                self.assertEqual(text_query_scope(query)['code'],'003')
            history.extend([{'role':'user','content':question},{'role':'assistant','content':'old response'}])
        scope=text_query_scope(query)
        self.assertEqual(scope['classes'],['ae','ar'])
        changed=build_retrieval_query('Yang tahun 2020, kode 004.',history)
        self.assertEqual(text_query_scope(changed)['year'],'2020')
        self.assertEqual(text_query_scope(changed)['code'],'004')
        self.assertEqual(build_retrieval_query('Jelaskan pengertian bangunan',history),'Jelaskan pengertian bangunan')

    def test_entire_transcript_is_context_without_thinking_or_cross_room_cache(self):
        history=[{'role':'user','content':'Objek MELATI tahun 2018'}]+[{'role':'assistant','content':'<think>PRIVATE_THINKING</think>Jawaban sebelumnya'} for _ in range(12)]
        prompt=build_chat_messages('yang tadi',history,[],[],0,'PBB-P2','konsultasi')
        self.assertIn('MELATI',str(prompt))
        self.assertIn('Jawaban sebelumnya',str(prompt))
        self.assertNotIn('PRIVATE_THINKING',str(prompt))
        self.assertNotIn('MELATI',str(build_chat_messages('halo',[],[],[],0,'PBB-P2','konsultasi')))
        self.assertTrue(prompt[-1]['content'].endswith('yang tadi'))
