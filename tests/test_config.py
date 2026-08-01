from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from equipdoc_agent.config import Settings


class SettingsTests(unittest.TestCase):
    def test_safe_defaults_use_demo_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env(Path(temp_dir))
            self.assertTrue(settings.demo_mode)
            self.assertFalse(settings.agentic_mode)
            self.assertEqual(settings.agent_max_steps, 3)
            self.assertEqual(settings.mode_name, "demo")
            self.assertEqual(settings.max_upload_bytes, 8 * 1024 * 1024)
            self.assertEqual(settings.upload_ttl_seconds, 24 * 60 * 60)
            self.assertEqual(settings.bearing_model_path, Path(temp_dir) / "models/bearing_cnn.pth")

    def test_boolean_and_relative_path_overrides(self):
        values = {
            "EQUIPDOC_DEMO_MODE": "false",
            "EQUIPDOC_MAX_UPLOAD_MB": "3",
            "EQUIPDOC_UPLOAD_ROOT": "tmp/uploads",
            "EQUIPDOC_UPLOAD_TTL_HOURS": "2",
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, values, clear=True):
            settings = Settings.from_env(Path(temp_dir))
            self.assertFalse(settings.demo_mode)
            self.assertEqual(settings.mode_name, "full")
            self.assertEqual(settings.max_upload_bytes, 3 * 1024 * 1024)
            self.assertEqual(settings.upload_root, Path(temp_dir) / "tmp/uploads")
            self.assertEqual(settings.upload_ttl_seconds, 2 * 60 * 60)

    def test_agentic_step_limit_is_clamped(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "EQUIPDOC_DEMO_MODE": "false",
                "EQUIPDOC_AGENTIC_MODE": "true",
                "EQUIPDOC_AGENT_MAX_STEPS": "99",
            },
            clear=True,
        ):
            settings = Settings.from_env(Path(temp_dir))
            self.assertTrue(settings.agentic_mode)
            self.assertEqual(settings.agent_max_steps, 4)

    def test_invalid_boolean_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {"EQUIPDOC_DEMO_MODE": "ture"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "EQUIPDOC_DEMO_MODE"):
                Settings.from_env(Path(temp_dir))


if __name__ == "__main__":
    unittest.main()
