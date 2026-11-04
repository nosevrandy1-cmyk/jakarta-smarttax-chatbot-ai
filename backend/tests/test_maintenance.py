from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import test_dashboard_empty as fixtures
from app.maintenance import reset_knowledge
from app.embedder import embedder
from test_ingestion_windows import make_pdf


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        fixtures.EmptyDashboardTests.setUp(self)
        self.store=fixtures.knowledge_store
        self.before_sources=len(self.store.archive.list())

    def test_reset_physically_removes_archived_and_orphan_vectors_and_preserves_backup(self):
        result=self.store.ingest_pdf(make_pdf('unique maintenance source'),'source.pdf')
        self.store.archive.activate(result['source_id'],'developer',self.store.collection,embedder)
        self.store.collection.upsert(ids=['orphan'],documents=['orphan text'],metadatas=[{'document_id':'deleted'}],embeddings=embedder.embed_texts(['orphan text']))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            engine=SimpleNamespace(history_path=root/'history.json',mirror_history_path=root/'mirror.json',golden_path=root/'golden.json')
            for path in vars(engine).values():path.write_text('[{"old":true}]',encoding='utf-8')
            output=reset_knowledge(self.store,engine,root/'backups')
            self.assertEqual(output['sources_removed'],self.before_sources+1)
            self.assertGreaterEqual(output['vectors_removed'],2)
            self.assertEqual(self.store.collection.count(),0)
            self.assertEqual(self.store.archive.list(),[])
            self.assertEqual(self.store.query_knowledge('unique maintenance source'),[])
            self.assertTrue((Path(output['backup_dir'])/'vectors.json').exists())
            self.assertTrue(list((Path(output['backup_dir'])/'files').glob('*.pdf')))
            self.assertTrue(all(p.read_text(encoding='utf-8')=='[]\n' for p in vars(engine).values()))
            self.assertEqual(reset_knowledge(self.store,engine,root/'backups')['sources_removed'],0)

    def test_backup_failure_does_not_delete_active_sources(self):
        result=self.store.ingest_pdf(make_pdf('maintenance failure'),'source.pdf')
        with tempfile.TemporaryDirectory() as folder:
            with patch('app.maintenance.Path.write_text',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):reset_knowledge(self.store,None,Path(folder))
        self.assertEqual(len(self.store.archive.list()),self.before_sources+1)


class MaintenanceAuthorizationTests(unittest.TestCase):
    def test_reset_requires_developer_and_csrf(self):
        import test_auth
        from app.auth import SESSION_COOKIE
        from app.maintenance import install_maintenance
        fixture=test_auth.GoogleAuthTests()
        fixture.setUp()
        try:
            install_maintenance(fixture.app,None,None,Path(fixture.temp.name)/"backups")
            token=fixture.store.create_session(fixture.claims,intent="register")
            session=fixture.store.session(token)
            async def check(client):
                with patch("app.maintenance.reset_knowledge") as reset:
                    self.assertEqual((await client.delete("/api/rag/sources")).status_code,401)
                    client.cookies.set(SESSION_COOKIE,token)
                    headers={"Origin":fixture.settings.public_url,"X-CSRF-Token":session["csrf"]}
                    self.assertEqual((await client.delete("/api/rag/sources",headers=headers)).status_code,403)
                    reset.assert_not_called()
            fixture.run_async(check)
        finally:fixture.tearDown()


class RetrievalCategoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_retrieval_uses_selected_tax_category(self):
        import json
        from app import ollama_service as chat
        from test_chat_grounding import Model
        Model.fail=False
        with patch.object(chat.knowledge_store,"query_knowledge",return_value=[]) as query, patch.object(chat.knowledge_store,"get_collection_telemetry",return_value={"total_chunks":0,"recent_sources":[]}),patch.object(chat.httpx,"AsyncClient",Model):
            events=[json.loads(event) async for event in chat.stream_smarttax_chat("Berapa pajak reklame saya?",[],tema_pajak="REKLAME")]
        query.assert_called_once_with("Berapa pajak reklame saya?",top_k=6,tema_pajak="REKLAME")
        self.assertTrue(any(event["type"]=="done" for event in events))

