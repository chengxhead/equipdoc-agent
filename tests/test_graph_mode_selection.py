from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
