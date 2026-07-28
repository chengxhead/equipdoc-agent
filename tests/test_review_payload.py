from __future__ import annotations

import unittest

from equipdoc_agent.agent.graph import _review_call_payload


class ReviewPayloadTests(unittest.TestCase):
    def test_hides_windows_server_path(self) -> None:
        payload = _review_call_payload(
            {
                "name": "diagnose_bearing",
                "args": {
                    "signal_path": (
                        r"C:\Users\MSI\Documents\portfolio\data\samples\test_signal.npy"
                    )
                },
            }
        )

        self.assertEqual(payload["args"], {"signal_file": "test_signal.npy"})
        self.assertNotIn("C:", str(payload))

    def test_preserves_non_path_arguments(self) -> None:
        payload = _review_call_payload(
            {"name": "example", "args": {"threshold": 0.5, "mode": "safe"}}
        )

        self.assertEqual(payload["args"], {"threshold": 0.5, "mode": "safe"})


if __name__ == "__main__":
    unittest.main()
