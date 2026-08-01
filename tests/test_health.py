from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from equipdoc_agent.config import Settings
from equipdoc_agent.health import collect_health


class HealthTests(unittest.TestCase):
    def test_public_health_report_hides_paths_and_endpoint(self):
        values = {
            "EQUIPDOC_LLM_BASE_URL": "http://private-model.internal:8000/v1",
            "EQUIPDOC_LLM_MODEL": "private-model-name",
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, values, clear=True
        ):
            settings = Settings.from_env(Path(temp_dir))
            report = collect_health(settings, public=True)
            rendered = repr(report)

        self.assertNotIn(str(Path(temp_dir)), rendered)
        self.assertNotIn("private-model.internal", rendered)
        self.assertIn("private-model-name configured", rendered)


if __name__ == "__main__":
    unittest.main()
