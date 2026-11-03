import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_dashboard_empty
from app import ollama_service as chat
from app import context_budget as budget
from app.context_budget import estimate_tokens, message_tokens, context_policy, room_fits
from test_chat_grounding import Model

class ContextBudgetTests(unittest.IsolatedAsyncioTestCase):
    def test_utf8_and_room_budget(self):
        self.assertEqual(estimate_tokens("税" * 12),12)
        with patch.object(budget,"ROOM_CONTEXT_BUDGET",0):p=context_policy("instructions")
        self.assertEqual(p["roomBudget"],max(0,p["limit"]-p["systemReserve"]-p["sourceReserve"]-p["replyReserve"]))
        self.assertFalse(room_fits([{"content":"x"*(p["limit"]*3)}],"halo",p))
        self.assertTrue(room_fits([],"halo",p))

    def test_test_budget_reduces_room_only_without_changing_model_capacity(self):
        with patch.object(budget,"ROOM_CONTEXT_BUDGET",0):normal=context_policy("instructions")
        with patch.object(budget,"ROOM_CONTEXT_BUDGET",256):small=context_policy("instructions")
        self.assertEqual(small["roomBudget"],min(normal["roomBudget"],256))
        for field in ["limit","systemReserve","sourceReserve","replyReserve"]:self.assertEqual(small[field],normal[field])
        self.assertFalse(room_fits([{"content":"x"*800}],"halo",small))
        with patch.object(budget,"ROOM_CONTEXT_BUDGET",999999):self.assertEqual(context_policy("instructions")["roomBudget"],normal["roomBudget"])

    async def test_oversized_single_source_does_not_call_model(self):
        hit=SimpleNamespace(doc_name="Large.pdf",text="x"*60000,model_dump=lambda:{"doc_name":"Large.pdf"})
        with patch.object(chat.knowledge_store,"query_knowledge",return_value=[hit]), patch.object(chat.knowledge_store,"get_collection_telemetry",return_value={"total_chunks":1,"recent_sources":[]}), patch.object(chat.httpx,"AsyncClient",side_effect=AssertionError("Must not invoke Ollama")):
            events=[json.loads(line) async for line in chat.stream_smarttax_chat("Jelaskan sumber ini",[])]
        self.assertTrue(any(e.get("code")=="request_context_limit" for e in events))
        self.assertFalse(any(e["type"]=="token" for e in events))

    async def test_sources_fit_as_whole_chunks_and_response_is_bounded(self):
        Model.fail=False
        hits=[SimpleNamespace(doc_name=f"Doc{i}.pdf",text="abc "*400,model_dump=lambda:{"doc_name":"test.pdf"}) for i in range(6)]
        with patch.object(chat.knowledge_store,"query_knowledge",return_value=hits), patch.object(chat.knowledge_store,"get_collection_telemetry",return_value={"total_chunks":6,"recent_sources":[]}), patch.object(chat.httpx,"AsyncClient",Model):
            events=[json.loads(line) async for line in chat.stream_smarttax_chat("Apa isi dokumen?",[])]
        request=Model.request;policy=chat.chat_context_policy()
        self.assertLess(message_tokens(request["messages"])+policy["replyReserve"],policy["limit"])
        self.assertGreaterEqual(request["options"]["num_predict"],policy["replyReserve"])
        self.assertLess(message_tokens(request["messages"])+request["options"]["num_predict"],policy["limit"])
        material=json.loads(request["messages"][-1]["content"].split("\n",1)[1].split("\n\nPERTANYAAN TERBARU",1)[0])
        self.assertGreater(len(material["kutipan_tersedia"]),0)
        self.assertLess(len(material["kutipan_tersedia"]),6)
        self.assertTrue(all(c["isi"]=="abc "*400 for c in material["kutipan_tersedia"]))

    def test_server_room_lookup_is_scoped_to_authenticated_owner(self):
        from app import main
        from app.chat_models import ChatRequestInput
        from fastapi import HTTPException
        calls=[]
        def lookup(owner,room):
            calls.append((owner,room))
            return {"messages":[{"content":"x"*60000}]} if room == 'owned' else None
        request=SimpleNamespace(state=SimpleNamespace(auth_user={"id":"user-A"}))
        with patch.object(main,"_auth_store",SimpleNamespace(history=SimpleNamespace(room=lookup))):
            with self.assertRaises(HTTPException) as caught:main.check_room_context(ChatRequestInput(message="halo",room_id="owned"),request)
            self.assertEqual(caught.exception.status_code,409)
            self.assertEqual(caught.exception.detail["code"],"room_context_limit")
            self.assertEqual(calls,[("user-A","owned")])
            main.check_room_context(ChatRequestInput(message="halo",room_id="different-room"),request)
            self.assertEqual(calls[-1],("user-A","different-room"))
