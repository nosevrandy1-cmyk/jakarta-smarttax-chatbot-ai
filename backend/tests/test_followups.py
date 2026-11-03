import json
import unittest
from unittest.mock import patch
import test_dashboard_empty
from app.followups import FollowUpStream, MARKER, CLOSING, validate_followups
from app import ollama_service as chat

class FollowUpParserTests(unittest.TestCase):
    def test_all_marker_split_positions_hide_metadata_and_keep_answer(self):
        text='Jawaban untuk pertanyaan Anda.\n'+MARKER+'["Bagaimana perhitungan untuk kategori Tirta?", "Apa syarat penggunaan untuk kesehatan?"]'+CLOSING
        for split in range(len(text)+1):
            stream=FollowUpStream('Jelaskan kategori Tirta')
            visible=stream.feed(text[:split])+stream.feed(text[split:])
            tail,questions=stream.finish()
            self.assertEqual((visible+tail).strip(),'Jawaban untuk pertanyaan Anda.')
            self.assertEqual(len(questions),2)
            self.assertNotIn('JST_FOLLOW',visible+tail)

    def test_single_character_stream_and_utf8_remain_intact(self):
        text='Keterangan café dan pajak. '+MARKER+'["Apa dasar perhitungannya?"]'+CLOSING
        stream=FollowUpStream('Tanya pajak');visible=''.join(stream.feed(c) for c in text);tail,questions=stream.finish()
        self.assertEqual(visible+tail,'Keterangan café dan pajak. ')
        self.assertEqual(questions,['Apa dasar perhitungannya?'])

    def test_missing_marker_leaves_answer_unchanged(self):
        for text in ['Jawaban tanpa saran.', 'Nilai < 100 dan daftar [1, 2].', 'Akhir <']:
            stream=FollowUpStream('Pertanyaan');visible=stream.feed(text);tail,questions=stream.finish()
            self.assertEqual(visible+tail,text);self.assertEqual(questions,[])

    def test_optional_metadata_failure_does_not_fail_main_answer(self):
        for metadata in ['["Pertanyaan yang terpotong?', '{"wrong":"type"}'+CLOSING, 'not JSON'+CLOSING, '[]'+CLOSING]:
            stream=FollowUpStream('Pertanyaan');visible=stream.feed('Jawaban tetap utuh.'+MARKER+metadata);tail,questions=stream.finish()
            self.assertEqual(visible+tail,'Jawaban tetap utuh.');self.assertEqual(questions,[])

    def test_truncated_marker_is_hidden(self):
        stream=FollowUpStream('Pertanyaan');visible=stream.feed('Jawaban.<JST_FOL');tail,questions=stream.finish()
        self.assertEqual(visible+tail,'Jawaban.');self.assertEqual(questions,[])

    def test_validation_filters_duplicates_echoes_urls_files_and_oversize_values(self):
        raw=['Apa nilai akhirnya?', 'Apa nilai akhirnya!!!', 'x', 42, 'Buka https://example.test', 'Upload dokumen berikut?', 'Apa <script> ini?', 'a'*161]
        self.assertEqual(validate_followups(raw,'Apa nilai akhirnya?'),[])
        self.assertEqual(validate_followups(['Apa syaratnya?', 'Apa syaratnya?', 'Bagaimana hitungannya?', 'Berapa hasilnya?'],'Halo'),['Apa syaratnya?', 'Bagaimana hitungannya?'])

    def test_missing_opener_bracket_and_lowercase_are_hidden_at_every_chunk_boundary(self):
        for opener,closing in [("<JST_FOLLOW_UPS",CLOSING),("<jst_follow_ups>","</jst_follow_ups>"),(MARKER,"</JST_FOLLOW_UPS")]:
            text='Jawaban rumus.'+opener+'["Bagaimana contoh perhitungan untuk objek tertentu?"]'+closing
            for split in range(len(text)+1):
                stream=FollowUpStream('Bagaimana rumusnya?')
                visible=stream.feed(text[:split])+stream.feed(text[split:]);tail,questions=stream.finish()
                self.assertEqual(visible+tail,'Jawaban rumus.')
                self.assertEqual(questions,['Bagaimana contoh perhitungan untuk objek tertentu?'])

    def test_metadata_buffer_is_bounded(self):
        stream=FollowUpStream('Tanya');stream.feed('Jawaban.'+MARKER);stream.feed('x'*20000)
        self.assertLessEqual(len(stream.metadata),4096);self.assertEqual(stream.finish(),('',[]))

class FakeReply:
    def __init__(self,text):self.text=text
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    def raise_for_status(self):pass
    async def aiter_lines(self):
        for char in self.text:yield json.dumps({'message':{'content':char}})

class FollowUpIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_model_request_returns_answer_and_its_generated_suggestions(self):
        calls=[]
        class Client:
            def __init__(self,*args,**kwargs):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            def stream(self,*args,**kwargs):
                calls.append(kwargs['json'])
                return FakeReply('Penjelasan koefisien Tirta.'+MARKER+'["Apa syarat pengurangan kategori Tirta?"]'+CLOSING)
        with patch.object(chat.knowledge_store,'query_knowledge',return_value=[]), patch.object(chat.knowledge_store,'get_collection_telemetry',return_value={'total_chunks':0,'recent_sources':[]}), patch.object(chat.httpx,'AsyncClient',Client):
            result=await chat.run_smarttax_chat('Jelaskan koefisien Tirta',[])
        self.assertEqual(len(calls),1)
        self.assertEqual(result['answer'],'Penjelasan koefisien Tirta.')
        self.assertEqual(result['follow_ups'],['Apa syarat pengurangan kategori Tirta?'])
        self.assertIn('pertanyaan terbaru DAN jawaban',calls[0]['messages'][0]['content'])
        self.assertNotIn(MARKER,result['answer'])

    async def test_progress_stages_follow_actual_retrieval_and_output(self):
        class Client:
            def __init__(self,*args,**kwargs):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            def stream(self,*args,**kwargs):return FakeReply('Jawaban.'+MARKER+'[]'+CLOSING)
        with patch.object(chat.knowledge_store,'query_knowledge',return_value=[]), patch.object(chat.knowledge_store,'get_collection_telemetry',return_value={'total_chunks':0,'recent_sources':[]}), patch.object(chat.httpx,'AsyncClient',Client):
            events=[json.loads(item) async for item in chat.stream_smarttax_chat('Jelaskan koefisien Tirta',[])]
        stages=[item['text'] for item in events if item['type']=='status']
        self.assertEqual(stages,['Mencari sumber…','Menyusun jawaban…','Menulis jawaban…','Menyiapkan saran lanjutan…'])
        kinds=[item['type'] for item in events]
        self.assertLess(kinds.index('sources'),next(i for i,item in enumerate(events) if item.get('text')=='Menyusun jawaban…'))
        self.assertLess(next(i for i,item in enumerate(events) if item.get('text')=='Menulis jawaban…'),kinds.index('token'))
