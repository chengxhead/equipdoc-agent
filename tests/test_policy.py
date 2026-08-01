from __future__ import annotations

import unittest

from equipdoc_agent.agent.policy import (
    normalize_review_decision,
    requests_diagnosis,
    should_run_diagnosis,
)


class PolicyTests(unittest.TestCase):
    def test_requires_signal_for_diagnosis(self):
        self.assertFalse(should_run_diagnosis("请诊断轴承", None))

    def test_signal_and_intent_trigger_diagnosis(self):
        self.assertTrue(should_run_diagnosis("帮我判断轴承有没有故障", "sample.npy"))

    def test_signal_without_diagnosis_intent_does_not_trigger(self):
        self.assertFalse(should_run_diagnosis("请记录这个文件", "sample.npy"))

    def test_attached_demo_signal_does_not_turn_knowledge_question_into_diagnosis(self):
        question = "轴承外圈出现局部点蚀时，包络谱通常有什么表现，现场应怎样交叉确认？"
        self.assertFalse(should_run_diagnosis(question, "sample.npy"))

    def test_diagnosis_concept_question_remains_knowledge_only_with_signal(self):
        self.assertFalse(
            should_run_diagnosis("为什么轴承故障诊断常用包络解调？", "sample.npy")
        )

    def test_explicit_current_signal_request_overrides_question_word(self):
        self.assertTrue(
            should_run_diagnosis("这段信号为什么异常？请帮我诊断。", "sample.npy")
        )

    def test_explicit_diagnosis_request_is_detected_without_a_signal(self):
        self.assertTrue(requests_diagnosis("请分析这段振动信号有没有轴承故障。"))
        self.assertFalse(requests_diagnosis("为什么轴承故障诊断常用包络解调？"))

    def test_equipment_runtime_question_is_not_a_diagnosis_action(self):
        question = "只根据一次振动采样，精确告诉我这个轴承还能运行多少天。"
        self.assertFalse(should_run_diagnosis(question, "sample.npy"))

    def test_review_decision_is_strict(self):
        self.assertEqual(normalize_review_decision(" Approve "), "approve")
        with self.assertRaises(ValueError):
            normalize_review_decision("yes")


if __name__ == "__main__":
    unittest.main()
