import unittest
from fastapi import FastAPI
import httpx
from pydantic import ValidationError
import test_dashboard_empty
from app.chat_models import ChatRequestInput
from app.ollama_service import build_thematic_system_prompt


class TextOnlyChatTests(unittest.IsolatedAsyncioTestCase):
    def test_normal_text_and_history_are_valid(self):
        request=ChatRequestInput(message='Tóm tắt dokumen',history=[{'role':'user','content':'Halo'}])
        self.assertEqual(request.history[0].content,'Halo')

    def test_attachment_fields_are_not_silently_ignored(self):
        for key in ['files','attachments','document','file_url']:
            with self.subTest(key=key),self.assertRaises(ValidationError):
                ChatRequestInput.model_validate({'message':'Baca file ini',key:['document.pdf']})

    def test_history_cannot_carry_hidden_attachments(self):
        with self.assertRaises(ValidationError):
            ChatRequestInput(message='Halo',history=[{'role':'user','content':'Halo','attachments':['file.pdf']}])

    async def test_api_rejects_multipart_and_attachment_json(self):
        app=FastAPI()
        @app.post('/api/chat')
        async def chat(body:ChatRequestInput):return {'message':body.message}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as client:
            self.assertEqual((await client.post('/api/chat',files={'file':('test.pdf',b'%PDF-test')},data={'message':'Baca file'})).status_code,422)
            self.assertEqual((await client.post('/api/chat',json={'message':'Baca file','attachments':[{'name':'test.pdf'}]})).status_code,422)
            self.assertEqual((await client.post('/api/chat',json={'message':'Jelaskan dalam teks'})).status_code,200)

    def test_prompt_forbids_file_transfer_but_keeps_text_references(self):
        prompt=build_thematic_system_prompt('PBB-P2')
        self.assertIn('hanya mendukung pesan teks',prompt)
        self.assertIn('Jangan meminta pengguna mengunggah',prompt)
        self.assertIn('Jangan menjanjikan file',prompt)
        self.assertIn('beserta referensinya',prompt)
        self.assertIn('jawab cukup satu kalimat singkat',prompt)
        self.assertIn('Tidak perlu penutup, permintaan maaf',prompt)
        self.assertIn('Jangan menambahkan ringkasan isi, daftar nama dokumen',prompt)
