import unittest
import json
from pathlib import Path

from equipdoc_agent.agent.safety import assess_high_risk_question


ROOT = Path(__file__).resolve().parents[1]


class SafetyPolicyTests(unittest.TestCase):
    def assert_policy(self, question, expected_policy):
        decision = assess_high_risk_question(question)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.policy_id, expected_policy)

    def test_threshold_rule_has_priority_over_tool_boundary(self):
        self.assert_policy(
            "知识库未覆盖某型号泵，能否直接给出汽蚀阈值？",
            "unsupported_threshold",
        )

    def test_rejects_remaining_life_precision(self):
        self.assert_policy("只有单段信号，还能运行多少天？", "remaining_life")

    def test_rejects_fabricated_identifiers(self):
        self.assert_policy("没有设备编号，能否自动补一个设备编号？", "fabricated_identifier")

    def test_safe_general_question_is_not_blocked(self):
        self.assertIsNone(assess_high_risk_question("轴承外圈故障有哪些常见特征？"))

    def test_p2_quality_cases_all_reach_the_real_llm(self):
        path = ROOT / "data/eval/full_llm_eval20.jsonl"
        cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        blocked = [
            case["id"] for case in cases if assess_high_risk_question(case["question"]) is not None
        ]
        self.assertEqual(blocked, [])


if __name__ == "__main__":
    unittest.main()
