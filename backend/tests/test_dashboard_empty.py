"""Run alone: python -m unittest discover -s tests -p test_dashboard_empty.py -v.

All database writes use a new temporary Chroma directory and temporary JSON
files. Nothing is inserted into the application's active data collection.
"""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

TEST_ROOT = Path(tempfile.mkdtemp(prefix="jst-dashboard-test-"))
os.environ["CHROMA_PERSIST_DIR"] = str(TEST_ROOT / "chroma")
os.environ["CHROMA_COLLECTION"] = "jst_dashboard_test"

from app import config
from app.eval_engine import SmartTaxEvaluationEngine
from app.rag_ingestion import SmartTaxChromaStore, chroma_store


class EmptyDashboardTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(config.CHROMA_STORAGE_DIR, (TEST_ROOT / "chroma").resolve())
        identifiers = chroma_store.collection.get()["ids"]
        if identifiers:
            chroma_store.collection.delete(ids=identifiers)
        chroma_store.last_ingested_source = None
        self.directory = TEST_ROOT / self._testMethodName
        self.directory.mkdir()
        self.engine = SmartTaxEvaluationEngine()
        self.engine.golden_path = self.directory / "golden.json"
        self.engine.history_path = self.directory / "history.json"
        self.engine.mirror_history_path = self.directory / "mirror.json"
        self.engine.golden_path.write_text("[]", encoding="utf-8")

    def add_source(self):
        return chroma_store.ingest_excel(
            b"kategori,keterangan\nPBB-P2,rujukan pengujian terisolasi\n",
            "test_only.csv", "PBB-P2", "Test runner",
        )

    def test_reads_and_queries_do_not_seed_empty_collection(self):
        for _ in range(2):
            telemetry = chroma_store.get_collection_telemetry()
            self.assertEqual(telemetry["total_chunks"], 0)
            self.assertEqual(telemetry["covered_slots"], 0)
            self.assertEqual(telemetry["recent_sources"], [])
            self.assertEqual(chroma_store.query_knowledge("test pajak"), [])
        self.assertEqual(chroma_store.collection.count(), 0)

    def test_empty_primary_history_does_not_restore_old_mirror(self):
        self.engine.history_path.write_text("[]", encoding="utf-8")
        self.engine.mirror_history_path.write_text('[{"snapshot_id":"legacy-demo"}]', encoding="utf-8")
        self.assertEqual(self.engine.load_history(), [])

    def test_missing_golden_dataset_has_no_fallback(self):
        self.engine.golden_path = self.directory / "not-created.json"
        self.assertEqual(self.engine.load_golden_dataset(), [])

    def test_reading_dashboard_does_not_create_scores_or_history(self):
        with patch("app.eval_engine.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=OSError("offline"))
            state = asyncio.run(self.engine.get_dashboard_state())
        self.assertIsNone(state["latest_snapshot"])
        self.assertEqual(state["history_timeline"], [])
        self.assertFalse(state["evaluation_readiness"]["ready"])
        self.assertFalse(self.engine.history_path.exists())
        self.assertFalse(self.engine.mirror_history_path.exists())

    def test_evaluation_requires_sources_and_dataset(self):
        with self.assertRaisesRegex(ValueError, "sumber data resmi"):
            self.engine.run_evaluation_sync()
        self.add_source()
        with self.assertRaisesRegex(ValueError, "Dataset uji resmi"):
            asyncio.run(self.engine.run_evaluation())
        self.assertEqual(self.engine.load_history(), [])
        self.assertFalse(self.engine.history_path.exists())

    def test_user_source_can_be_ingested_without_dataset(self):
        result = self.add_source()
        self.assertEqual(result["rows_ingested"], 1)
        telemetry = chroma_store.get_collection_telemetry()
        self.assertEqual(telemetry["total_chunks"], 1)
        self.assertEqual(telemetry["recent_sources"][0]["doc_name"], "test_only.csv")
        self.assertFalse(self.engine.evaluation_readiness()["ready"])
        self.assertEqual(self.engine.load_history(), [])

    def test_actual_evaluation_records_only_the_available_question(self):
        self.add_source()
        question = {"id":"TEST-001", "domain":"PBB-P2", "pertanyaan":"Apa keterangan rujukan?",
                    "kunci_jawaban":"rujukan pengujian terisolasi", "kata_kunci_wajib":["rujukan"]}
        self.engine.golden_path.write_text(json.dumps([question]), encoding="utf-8")
        snapshot = self.engine.run_evaluation_sync(trigger_event="Test terisolasi")
        self.assertEqual(len(snapshot["items"]), 1)
        self.assertEqual(snapshot["items"][0]["id"], "TEST-001")
        history = self.engine.load_history()
        self.assertEqual(len(history), 1)
        self.assertNotIn("baseline", history[0]["snapshot_id"])
        self.assertEqual(history[0]["total_chunks_indexed"], 1)

    def test_reopening_store_does_not_seed(self):
        reopened = SmartTaxChromaStore()
        self.assertEqual(reopened.collection.count(), 0)
        self.assertEqual(reopened.get_collection_telemetry()["total_chunks"], 0)


if __name__ == "__main__":
    unittest.main()
