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
            self.assertEqual(settings.max_upload_bytes, 8 * 1024 * 1024)
            self.assertEqual(settings.bearing_model_path, Path(temp_dir) / "models/bearing_cnn.pth")

    def test_boolean_and_relative_path_overrides(self):
        values = {
            "EQUIPDOC_DEMO_MODE": "false",
            "EQUIPDOC_MAX_UPLOAD_MB": "3",
            "EQUIPDOC_UPLOAD_ROOT": "tmp/uploads",
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, values, clear=True):
            settings = Settings.from_env(Path(temp_dir))
            self.assertFalse(settings.demo_mode)
            self.assertEqual(settings.max_upload_bytes, 3 * 1024 * 1024)
            self.assertEqual(settings.upload_root, Path(temp_dir) / "tmp/uploads")


if __name__ == "__main__":
    unittest.main()

