from __future__ import annotations

import unittest

from equipdoc_agent.agent.reporting import render_diagnosis_report


class ReportingTests(unittest.TestCase):
    def test_demo_report_is_explicitly_labelled(self):
        report = render_diagnosis_report(
            {
                "mode": "demo_fixture",
                "fault_type": "外圈故障（固定演示案例）",
                "confidence": None,
                "probabilities": {},
                "warning": "fixture",
            },
            "test_signal.npy",
        )
        self.assertIn("Demo 提示", report)
        self.assertIn("不是模型推理结果", report)
        self.assertIn("不根据单段信号推断精确剩余寿命", report)


if __name__ == "__main__":
    unittest.main()

