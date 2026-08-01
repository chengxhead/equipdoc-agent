from __future__ import annotations

import unittest
from pathlib import Path

from equipdoc_agent.privacy import public_exception_message, redact_sensitive_text


class PrivacyTests(unittest.TestCase):
    def test_paths_and_credentials_are_redacted(self):
        root = Path("C:/Users/example/private-project")
        rendered = redact_sensitive_text(
            "failed at C:/Users/example/private-project/runtime/file.npy "
            "with Authorization: Bearer secret-value and api_key=another-secret",
            project_root=root,
        )
        self.assertNotIn("private-project", rendered)
        self.assertNotIn("secret-value", rendered)
        self.assertNotIn("another-secret", rendered)
        self.assertIn("[REDACTED_PATH]", rendered)

    def test_unexpected_exception_details_are_not_public(self):
        rendered = public_exception_message(RuntimeError("database password is hunter2"))
        self.assertNotIn("hunter2", rendered)
        self.assertIn("RuntimeError", rendered)


if __name__ == "__main__":
    unittest.main()
