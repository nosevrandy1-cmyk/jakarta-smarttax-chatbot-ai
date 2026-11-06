import json
import unittest
from unittest.mock import patch
import test_dashboard_empty
from app import ollama_service as chat
from app.followups import FollowUpStream
from app.tax_navigation import explicit_other_tax, validated_destination, fast_navigation_request, validated_destinations
from test_followups import FakeReply


class TaxNavigationTests(unittest.IsolatedAsyncioTestCase):
    def test_only_single_explicit_other_category_takes_fast_path(self):
        self.assertEqual(explicit_other_tax('kamu tau pajak air tanah', 'PBB-P2'), 'PAT')
        for question in ['Tarif PBB?', 'Apa beda PBB dan BPHTB?', 'BPHTB dan reklame', 'tempat bayar pajak', 'air tnah']:
            self.assertIsNone(explicit_other_tax(question, 'PBB-P2'))

    def test_invalid_uncertain_same_category_and_truncated_metadata_do_not_route(self):
        for theme, confidence in [('UNKNOWN','high'), ('PAT','low'), ('PBB-P2','high'), (['PAT'],'high')]:
            parser=FollowUpStream('Pertanyaan')
            parser.feed('Jawaban.<JST_FOLLOW_UPS>'+json.dumps({'suggested_theme':theme,'confidence':confidence,'questions':[]})+'</JST_FOLLOW_UPS>')
            parser.finish()
            self.assertIsNone(validated_destination(parser, 'PBB-P2'))
        parser=FollowUpStream('Pertanyaan')
        parser.feed('Jawaban.<JST_FOLLOW_UPS>{"suggested_theme":"PAT"')
        parser.finish()
        self.assertIsNone(validated_destination(parser, 'PBB-P2'))

    async def test_fast_path_uses_one_model_call_no_sources_no_thinking_and_model_destination(self):
        calls=[]
        class Client:
            def __init__(self,*args,**kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            def stream(self,*args,**kwargs):
                calls.append(kwargs['json'])
                return FakeReply('{"answer":"Mari lanjutkan di kategori Air Tanah.","suggested_themes":["PAT"],"confidence":"high"}')
        with patch.object(chat.knowledge_store,'query_knowledge',side_effect=AssertionError('No retrieval')), patch.object(chat.knowledge_store,'get_collection_telemetry',side_effect=AssertionError('No inventory')), patch.object(chat.httpx,'AsyncClient',Client):
            events=[json.loads(item) async for item in chat.stream_smarttax_chat('kamu tau pajak air tanah',[],model='gemma4:12b')]
        self.assertEqual(len(calls),1)
        self.assertFalse(calls[0]['think'])
        self.assertLessEqual(calls[0]['options']['num_predict'],384)
        self.assertEqual(events[-1]['suggested_theme'],'PAT')
        self.assertEqual(events[-1]['references'],[])
        self.assertEqual(events[-1]['follow_ups'],[])
        self.assertNotIn('JST_FOLLOW',events[-1]['answer'])
        self.assertFalse(any(item['type']=='sources' for item in events))

    async def test_invalid_structured_output_fails_without_creating_a_navigation_button(self):
        from test_chat_grounding import Model
        with patch.object(chat.httpx,'AsyncClient',Model):
            events=[json.loads(item) async for item in chat.stream_smarttax_chat('pajak air tanah',[])]
        self.assertEqual(events[-1]['response_source'],'unavailable')

    def test_object_metadata_preserves_normal_followup_questions(self):
        parser=FollowUpStream('Apa rumusnya?')
        raw='Jawaban.<JST_FOLLOW_UPS>{"questions":["Bagaimana contoh perhitungannya?"],"suggested_theme":null,"confidence":"low"}</JST_FOLLOW_UPS>'
        visible=''.join(parser.feed(char) for char in raw)
        tail,questions=parser.finish()
        self.assertEqual(visible+tail,'Jawaban.')
        self.assertEqual(questions,['Bagaimana contoh perhitungannya?'])

    def test_two_categories_typo_and_out_of_scope_take_lightweight_path(self):
        for question in ['apa beda BPHTB sama pajak reklame?', 'jelasin pajak air tnah dong', 'jelaskan pajak penghasilan']:
            self.assertTrue(fast_navigation_request(question, 'PBB-P2'))
        self.assertEqual(validated_destinations(['BPHTB','REKLAME','PAT'],'high','PBB-P2'),['BPHTB','REKLAME'])
        self.assertEqual(validated_destinations(['PAT'],'low','PBB-P2'),[])
