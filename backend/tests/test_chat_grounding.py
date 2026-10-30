import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
# Initialize the shared temporary data environment before importing the app,
# so discovery order cannot connect this suite to the active collection.
import test_dashboard_empty
from app import ollama_service as chat


class Reply:
    def __init__(self, text): self.text=text
    async def __aenter__(self): return self
    async def __aexit__(self,*args): pass
    def raise_for_status(self): pass
    async def aiter_lines(self):
        yield json.dumps({"message":{"content":self.text}})


class Model:
    request=None
    fail=False
    def __init__(self,*args,**kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self,*args): pass
    def stream(self,*args,**kwargs):
        Model.request=kwargs["json"]
        if Model.fail: raise OSError("model offline")
        return Reply("Jawaban model untuk pengujian.")


class ChatGroundingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        Model.fail=False
        self.store=SimpleNamespace(query_knowledge=lambda *a,**k:[],
            get_collection_telemetry=lambda:{"recent_sources":[],"total_chunks":0})

    async def events(self, question, history=None):
        with patch.object(chat,"chroma_store",self.store), patch.object(chat.httpx,"AsyncClient",Model):
            return [json.loads(line) async for line in chat.stream_smarttax_chat(question,history or [])]

    async def test_greeting_and_tax_questions_use_model_not_templates(self):
        for question in ["Halo", "Apa informasi yang kamu punya?", "Tarif PBB berapa?", "Bagaimana BPHTB?"]:
            events=await self.events(question)
            self.assertEqual(''.join(e.get("delta","") for e in events),"Jawaban model untuk pengujian.")
            self.assertEqual(events[-1]["response_source"],"ollama")
            self.assertFalse(any(e["type"]=="thinking" for e in events))
            prompt=json.loads(Model.request["messages"][-1]["content"].split("\n",1)[1].split("\n\nPERTANYAAN TERBARU",1)[0])
            self.assertEqual(prompt["daftar_dokumen"],[])
            self.assertEqual(prompt["kutipan_tersedia"],[])

    async def test_legacy_assistant_claims_are_not_reused_as_context(self):
        await self.events("Apa datanya?",[{"role":"assistant","content":"Hunian Puri Indah NJOP 5,8 miliar"}])
        self.assertNotIn("Puri Indah",json.dumps(Model.request))

    async def test_prd_is_passed_as_document_not_replaced_with_tax_data(self):
        self.store.get_collection_telemetry=lambda:{"total_chunks":1,"recent_sources":[
            {"doc_name":"PRD JST.pdf","source_type":"pdf_regulasi","domain":"PBB-P2"}]}
        hit=SimpleNamespace(doc_name="PRD JST.pdf",text="Rencana fitur login Google dan history per pengguna.",model_dump=lambda:{"doc_name":"PRD JST.pdf"})
        self.store.query_knowledge=lambda *a,**k:[hit]
        await self.events("Informasi apa yang tersedia?")
        request=json.dumps(Model.request,ensure_ascii=False)
        self.assertIn("login Google",request)
        self.assertNotIn("60.000.000",request)
        self.assertNotIn("SCBD",request)
        self.assertIn("PRD bukan dasar hukum",request)

    async def test_latest_question_is_only_live_user_turn(self):
        history = [{"role":"user","content":"Apa tujuan JST-UJI-001?"},
            {"role":"assistant","content":"Jawaban lama yang bukan bukti."},
            {"role":"user","content":"Berapa koefisien Uji B?"}]
        await self.events("Berapa hasil simulasi Gedung Latihan Biru?", history)
        messages = Model.request["messages"]
        self.assertEqual([m["role"] for m in messages], ["system", "user"])
        self.assertTrue(messages[-1]["content"].endswith("Berapa hasil simulasi Gedung Latihan Biru?"))
        self.assertIn("pertanyaan_lama_sudah_selesai", messages[-1]["content"])
        self.assertNotIn("Jawaban lama yang bukan bukti", str(messages))

    async def test_sequential_requests_keep_current_question_last(self):
        history=[]
        for question in ["Apa tujuan JST-UJI-001?", "Berapa koefisien Uji B?", "Berapa hasil simulasi gedung?", "Apakah tarif ini resmi?"]:
            await self.events(question, history)
            user_turns=[m for m in Model.request["messages"] if m["role"]=="user"]
            self.assertEqual(len(user_turns),1)
            self.assertEqual(user_turns[0]["content"].rsplit("\n",1)[-1],question)
            history.extend([{"role":"user","content":question},{"role":"assistant","content":"jawaban selesai"}])

    async def test_offline_model_reports_failure_without_fabricated_answer(self):
        Model.fail=True
        events=await self.events("Tarif pajak?")
        self.assertFalse(any(e["type"] in ("token","thinking") for e in events))
        self.assertTrue(any(e["type"]=="error" for e in events))
        self.assertEqual(events[-1]["response_source"],"unavailable")


if __name__=="__main__": unittest.main()
