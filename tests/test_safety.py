import unittest

from equipdoc_agent.agent.safety import assess_high_risk_question


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


if __name__ == "__main__":
    unittest.main()
