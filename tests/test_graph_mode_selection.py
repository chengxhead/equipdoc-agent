from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from equipdoc_agent.agent.graph import build_graph
from equipdoc_agent.config import Settings


class GraphModeSelectionTests(unittest.TestCase):
    def test_full_agentic_mode_uses_the_independent_graph(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = replace(
                Settings.from_env(Path(temp_dir)),
                demo_mode=False,
                agentic_mode=True,
            )
            sentinel = object()
            with patch(
                "equipdoc_agent.agent.agentic_graph.build_agentic_graph",
                return_value=sentinel,
            ) as builder:
                result = build_graph(settings)
        self.assertIs(result, sentinel)
        builder.assert_called_once_with(settings)

    def test_demo_mode_ignores_agentic_opt_in(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = replace(
                Settings.from_env(Path(temp_dir)),
                demo_mode=True,
                agentic_mode=True,
            )
            with patch(
                "equipdoc_agent.agent.agentic_graph.build_agentic_graph"
            ) as builder:
                result = build_graph(settings)
        builder.assert_not_called()
        self.assertIsNotNone(result)

    def test_demo_thread_clears_removed_signal_and_requests_upload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = replace(
                Settings.from_env(Path(temp_dir)),
                demo_mode=True,
                agentic_mode=False,
                rag_enabled=False,
            )
            graph = build_graph(settings)
            config = {"configurable": {"thread_id": "demo_signal_clear"}}
            pending = graph.invoke(
                {
                    "messages": [HumanMessage(content="请诊断这段轴承信号。")],
                    "signal_path": "old-signal.npy",
                },
                config=config,
            )
            self.assertIn("__interrupt__", pending)
            graph.invoke(Command(resume="reject"), config=config)

            result = graph.invoke(
                {
                    "messages": [HumanMessage(content="请分析这段振动信号有没有轴承故障。")],
                    "signal_path": "",
                },
                config=config,
            )

        self.assertNotIn("__interrupt__", result)
        self.assertIn("请上传", str(result["messages"][-1].content))

    def test_demo_safety_boundary_preempts_diagnosis_when_signal_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = replace(
                Settings.from_env(Path(temp_dir)),
                demo_mode=True,
                agentic_mode=False,
                rag_enabled=False,
            )
            graph = build_graph(settings)
            result = graph.invoke(
                {
                    "messages": [
                        HumanMessage(
                            content="只根据一次振动采样，精确告诉我这个轴承还能运行多少天。"
                        )
                    ],
                    "signal_path": "sample.npy",
                },
                config={"configurable": {"thread_id": "demo_safety_preemption"}},
            )

        self.assertNotIn("__interrupt__", result)
        self.assertIn("无法", str(result["messages"][-1].content))


if __name__ == "__main__":
    unittest.main()
