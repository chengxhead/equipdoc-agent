from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from equipdoc_agent.agent.agentic_tools import (
    execute_agentic_tool,
    search_maintenance_knowledge,
)
from equipdoc_agent.config import Settings


class _FakeRetriever:
    warnings = ["vector DB unavailable"]

    def __init__(self):
        self.calls = []

    def search(self, query, filters=None, top_k=None):
        self.calls.append((query, filters, top_k))
        return [
            {
                "doc_id": "bearing_outer_race_fault",
                "chunk_id": "bearing_outer_race_fault_c001",
                "title": "轴承外圈故障",
                "text": "外圈缺陷会产生周期性冲击。",
                "rrf_score": 0.02,
                "lexical_score": 4.5,
            }
        ]


class AgenticToolTests(unittest.TestCase):
    def test_search_returns_citation_ready_structured_hits(self):
        retriever = _FakeRetriever()
        result = search_maintenance_knowledge(
            retriever,
            query="外圈故障",
            equipment="bearing",
            fault_type="outer_race",
            top_k=3,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["hits"][0]["citation"],
            "bearing_outer_race_fault#bearing_outer_race_fault_c001",
        )
        self.assertEqual(
            retriever.calls,
            [("外圈故障", {"equipment": "bearing", "fault_type": "outer_race"}, 3)],
        )

    def test_search_rejects_invalid_filters_and_top_k(self):
        with self.assertRaises(ValueError):
            search_maintenance_knowledge(
                _FakeRetriever(),
                query="轴承",
                equipment="unknown",
            )
        with self.assertRaises(ValueError):
            search_maintenance_knowledge(_FakeRetriever(), query="轴承", top_k=6)

    def test_missing_retriever_is_an_explicit_error(self):
        result = search_maintenance_knowledge(None, query="轴承")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["hits"], [])

    def test_inspect_signal_executes_read_only_and_hides_absolute_path(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True):
            root = Path(temp_dir)
            sample_root = root / "data/samples"
            sample_root.mkdir(parents=True)
            sample = sample_root / "inspect.npy"
            np.save(sample, np.arange(32, dtype=np.float32))
            settings = Settings.from_env(root)
            settings.ensure_runtime_dirs()
            result = execute_agentic_tool(
                "inspect_signal",
                {"signal_path": "C:\\model-supplied\\bad.npy"},
                signal_path=str(sample),
                settings=settings,
                retriever=None,
            )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["_tool_name"], "inspect_signal")
        self.assertEqual(result["signal_file"], "inspect.npy")
        self.assertNotIn("signal_path", result)
        self.assertIn("少于1024", result["warnings"][0])

    def test_unknown_tool_is_not_executed(self):
        settings = Settings.from_env(Path.cwd())
        result = execute_agentic_tool(
            "delete_signal",
            {},
            signal_path=None,
            settings=settings,
            retriever=None,
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("Unknown tool", result["error"])


if __name__ == "__main__":
    unittest.main()
