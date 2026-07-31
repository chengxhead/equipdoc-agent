from __future__ import annotations

import json
import unittest

from equipdoc_agent.agent.planning import (
    PlanningValidationError,
    build_intent_plan_messages,
    build_intent_plan_retry_messages,
    build_observation_messages,
    extract_json_object,
    fallback_plan,
    parse_and_validate_plan,
    parse_observation_decision,
)


def _plan_text(**overrides) -> str:
    payload = {
        "intent": "knowledge_qa",
        "confidence": 0.91,
        "equipment": "bearing",
        "missing_fields": [],
        "clarification_question": "",
        "plan": [
            {
                "step_id": "S1",
                "tool": "search_maintenance_knowledge",
                "arguments": {
                    "query": "轴承外圈故障 周期性冲击 现场复核",
                    "equipment": "bearing",
                    "fault_type": "outer_race",
                    "top_k": 5,
                },
                "depends_on": [],
            }
        ],
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


class AgenticPlanningTests(unittest.TestCase):
    def test_extracts_json_from_code_fence_and_surrounding_text(self):
        raw = '说明文字\n```json\n{"intent":"knowledge_qa","nested":{"text":"{}"}}\n```\n结束'
        self.assertEqual(extract_json_object(raw)["nested"]["text"], "{}")

    def test_valid_knowledge_plan_is_normalized(self):
        plan = parse_and_validate_plan(_plan_text(), max_steps=3)
        self.assertEqual(plan["intent"], "knowledge_qa")
        self.assertEqual(plan["plan"][0]["tool"], "search_maintenance_knowledge")
        self.assertEqual(plan["plan"][0]["arguments"]["top_k"], 5)
        self.assertEqual(plan["validation"]["source"], "model")

    def test_diagnosis_without_signal_becomes_clarification(self):
        text = _plan_text(
            intent="diagnosis",
            plan=[
                {
                    "step_id": "S1",
                    "tool": "diagnose_bearing",
                    "arguments": {},
                    "depends_on": [],
                }
            ],
        )
        plan = parse_and_validate_plan(text, has_signal=False)
        self.assertEqual(plan["intent"], "clarification")
        self.assertEqual(plan["plan"], [])
        self.assertIn("signal", plan["missing_fields"])
        self.assertIn(".npy", plan["clarification_question"])

    def test_self_contained_knowledge_question_rejects_clarification(self):
        clarification = _plan_text(
            intent="clarification",
            missing_fields=["operating_condition"],
            clarification_question="请补充具体工况。",
            plan=[],
        )
        with self.assertRaisesRegex(
            PlanningValidationError,
            "self-contained maintenance knowledge question",
        ):
            parse_and_validate_plan(
                clarification,
                user_text="管道泄漏声振诊断应关注哪些数据和常见误报来源？",
            )

        executable_request = parse_and_validate_plan(
            clarification,
            user_text="请诊断这个轴承信号。",
        )
        self.assertEqual(executable_request["intent"], "clarification")

    def test_model_signal_path_is_removed_from_tool_arguments(self):
        text = _plan_text(
            intent="diagnosis",
            plan=[
                {
                    "step_id": "S1",
                    "tool": "diagnose_bearing",
                    "arguments": {"signal_path": "C:\\private\\signal.npy"},
                    "depends_on": [],
                }
            ],
        )
        plan = parse_and_validate_plan(text, has_signal=True)
        self.assertEqual(plan["plan"][0]["arguments"], {})
        self.assertEqual(
            plan["validation"]["removed_arguments"],
            [{"step_id": "S1", "field": "signal_path"}],
        )

    def test_unknown_tool_and_unknown_arguments_are_rejected(self):
        unknown_tool = _plan_text(
            plan=[
                {
                    "step_id": "S1",
                    "tool": "delete_signal",
                    "arguments": {},
                    "depends_on": [],
                }
            ]
        )
        with self.assertRaises(PlanningValidationError):
            parse_and_validate_plan(unknown_tool)

        unknown_argument = _plan_text()
        payload = json.loads(unknown_argument)
        payload["plan"][0]["arguments"]["server_path"] = "/tmp/private"
        with self.assertRaises(PlanningValidationError):
            parse_and_validate_plan(json.dumps(payload, ensure_ascii=False))

    def test_step_limit_duplicate_id_and_dependency_cycle_are_rejected(self):
        step = {
            "tool": "search_maintenance_knowledge",
            "arguments": {"query": "轴承", "top_k": 1},
        }
        too_many = _plan_text(
            plan=[
                {**step, "step_id": "S1", "depends_on": []},
                {**step, "step_id": "S2", "depends_on": ["S1"]},
            ]
        )
        with self.assertRaises(PlanningValidationError):
            parse_and_validate_plan(too_many, max_steps=1)

        duplicate = _plan_text(
            plan=[
                {**step, "step_id": "S1", "depends_on": []},
                {**step, "step_id": "S1", "depends_on": []},
            ]
        )
        with self.assertRaises(PlanningValidationError):
            parse_and_validate_plan(duplicate)

        cycle = _plan_text(
            plan=[
                {**step, "step_id": "S1", "depends_on": ["S2"]},
                {**step, "step_id": "S2", "depends_on": ["S1"]},
            ]
        )
        with self.assertRaises(PlanningValidationError):
            parse_and_validate_plan(cycle)

    def test_search_parameters_are_bounded(self):
        payload = json.loads(_plan_text())
        payload["plan"][0]["arguments"]["top_k"] = 6
        with self.assertRaises(PlanningValidationError):
            parse_and_validate_plan(json.dumps(payload, ensure_ascii=False))
        payload["plan"][0]["arguments"]["top_k"] = True
        with self.assertRaises(PlanningValidationError):
            parse_and_validate_plan(json.dumps(payload, ensure_ascii=False))

    def test_prompts_include_constraints_and_hide_server_paths(self):
        messages = build_intent_plan_messages(
            "检查上一轮结果",
            memory={
                "signal_file": "safe.npy",
                "signal_path": "C:\\secret\\safe.npy",
                "last_diagnosis": {"fault_type": "外圈故障"},
            },
            has_signal=True,
            max_steps=3,
        )
        combined = "\n".join(str(message.content) for message in messages)
        self.assertIn("plan 最多 3 步", combined)
        self.assertIn("safe.npy", combined)
        self.assertNotIn("C:\\secret", combined)

        retry = build_intent_plan_retry_messages(
            "检查上一轮结果",
            rejected_output="bad",
            validation_error="Unknown tool",
        )
        self.assertIn("Unknown tool", str(retry[-1].content))

    def test_fallback_preserves_safety_and_missing_signal_boundaries(self):
        safety = fallback_plan("请精确告诉我轴承还能运行多少天")
        self.assertEqual(safety["intent"], "safety_boundary")
        self.assertEqual(safety["plan"], [])

        clarification = fallback_plan("请诊断这个轴承", has_signal=False)
        self.assertEqual(clarification["intent"], "clarification")
        self.assertIn("signal", clarification["missing_fields"])

        diagnosis = fallback_plan("请诊断这个轴承", has_signal=True)
        self.assertEqual(diagnosis["plan"][0]["tool"], "diagnose_bearing")

        knowledge = fallback_plan(
            "管道泄漏声振诊断应关注哪些数据和常见误报来源？",
            has_signal=False,
        )
        self.assertEqual(knowledge["intent"], "knowledge_qa")
        self.assertEqual(
            knowledge["plan"][0]["tool"],
            "search_maintenance_knowledge",
        )

    def test_observation_decision_enforces_permissions_and_remaining_steps(self):
        raw = json.dumps(
            {
                "action": "call_tool",
                "tool": "search_maintenance_knowledge",
                "arguments": {"query": "外圈故障现场复核", "top_k": 3},
                "reason": "补充证据",
                "clarification_question": "",
            },
            ensure_ascii=False,
        )
        decision = parse_observation_decision(
            raw,
            permitted_tools={"search_maintenance_knowledge"},
            remaining_steps=1,
        )
        self.assertEqual(decision["action"], "call_tool")

        with self.assertRaises(PlanningValidationError):
            parse_observation_decision(
                raw,
                permitted_tools={"inspect_signal"},
                remaining_steps=1,
            )
        with self.assertRaises(PlanningValidationError):
            parse_observation_decision(
                raw,
                permitted_tools={"search_maintenance_knowledge"},
                remaining_steps=0,
            )

    def test_observation_signal_tool_without_signal_becomes_clarification(self):
        raw = json.dumps(
            {
                "action": "call_tool",
                "tool": "inspect_signal",
                "arguments": {"signal_path": "/private/file.npy"},
                "reason": "读取摘要",
                "clarification_question": "",
            },
            ensure_ascii=False,
        )
        decision = parse_observation_decision(
            raw,
            permitted_tools={"inspect_signal"},
            remaining_steps=1,
            has_signal=False,
        )
        self.assertEqual(decision["action"], "clarify")
        self.assertIn(".npy", decision["clarification_question"])
        self.assertNotIn("signal_path", decision["arguments"])

    def test_observation_prompt_redacts_structured_paths(self):
        messages = build_observation_messages(
            "下一步做什么？",
            current_plan={"intent": "diagnosis"},
            observations=[
                {
                    "status": "ok",
                    "signal_path": "C:\\secret\\file.npy",
                    "signal_file": "file.npy",
                }
            ],
            permitted_tools={"search_maintenance_knowledge"},
            remaining_steps=1,
        )
        combined = "\n".join(str(message.content) for message in messages)
        self.assertNotIn("C:\\secret", combined)
        self.assertIn("file.npy", combined)


if __name__ == "__main__":
    unittest.main()
