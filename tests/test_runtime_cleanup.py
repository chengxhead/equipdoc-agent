from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from equipdoc_agent.config import Settings
from equipdoc_agent.runtime_cleanup import cleanup_stale_uploads


class RuntimeCleanupTests(unittest.TestCase):
    def test_only_expired_app_staged_signals_are_removed(self):
        values = {"EQUIPDOC_UPLOAD_TTL_HOURS": "1"}
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, values, clear=True
        ):
            settings = Settings.from_env(Path(temp_dir))
            settings.ensure_runtime_dirs()
            expired = settings.upload_root / ("a" * 32 + ".npy")
            recent = settings.upload_root / ("b" * 32 + ".npy")
            user_named = settings.upload_root / "important.npy"
            for path in (expired, recent, user_named):
                path.write_bytes(b"test")
            now = 100_000.0
            os.utime(expired, (now - 7200, now - 7200))
            os.utime(recent, (now - 60, now - 60))
            os.utime(user_named, (now - 7200, now - 7200))

            result = cleanup_stale_uploads(settings, now=now)

            self.assertEqual(result, {"removed": 1, "failed": 0})
            self.assertFalse(expired.exists())
            self.assertTrue(recent.exists())
            self.assertTrue(user_named.exists())


if __name__ == "__main__":
    unittest.main()
