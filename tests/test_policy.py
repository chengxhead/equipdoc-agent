from __future__ import annotations

import unittest

from equipdoc_agent.agent.policy import normalize_review_decision, should_run_diagnosis


class PolicyTests(unittest.TestCase):
    def test_requires_signal_for_diagnosis(self):
        self.assertFalse(should_run_diagnosis("请诊断轴承", None))

    def test_signal_and_intent_trigger_diagnosis(self):
        self.assertTrue(should_run_diagnosis("帮我判断轴承有没有故障", "sample.npy"))

    def test_signal_without_diagnosis_intent_does_not_trigger(self):
        self.assertFalse(should_run_diagnosis("请记录这个文件", "sample.npy"))

    def test_review_decision_is_strict(self):
        self.assertEqual(normalize_review_decision(" Approve "), "approve")
        with self.assertRaises(ValueError):
            normalize_review_decision("yes")


if __name__ == "__main__":
    unittest.main()

