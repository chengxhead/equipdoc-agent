from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from equipdoc_agent.agent.planning import fallback_plan
from equipdoc_agent.agent.safety import assess_high_risk_question
from scripts.eval_agentic_full import _load_jsonl, _validate_cases


ROOT = Path(__file__).resolve().parents[1]
DEMO_EVAL = ROOT / "data/eval/agentic_demo.jsonl"
FORMAL_EVAL = ROOT / "data/eval/agentic_eval.jsonl"
SMOKE_EVAL = ROOT / "data/eval/agentic_smoke.jsonl"
DEMO_EVAL_SHA256 = "1a2070b173b97e17951e10baba329bd77a1fdf3279850f4db536eb3b9e72ff57"


class AgenticDemoDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = _load_jsonl(DEMO_EVAL)

    def test_schema_size_and_hash_are_frozen(self):
        _validate_cases(self.cases)
        self.assertEqual(len(self.cases), 12)
        self.assertEqual(sum(len(case["turns"]) for case in self.cases), 13)
        self.assertEqual(
            hashlib.sha256(DEMO_EVAL.read_bytes()).hexdigest(),
            DEMO_EVAL_SHA256,
        )

    def test_questions_are_independent_from_smoke_and_formal_sets(self):
        reference_questions = {
            turn["question"]
            for path in (FORMAL_EVAL, SMOKE_EVAL)
            for case in _load_jsonl(path)
            for turn in case["turns"]
        }
        demo_questions = [
            turn["question"] for case in self.cases for turn in case["turns"]
        ]
        self.assertEqual(len(demo_questions), len(set(demo_questions)))
        self.assertTrue(reference_questions.isdisjoint(demo_questions))

    def test_safe_fallback_matches_every_expected_intent(self):
        mismatches = []
        for case in self.cases:
            has_signal = False
            for turn_index, turn in enumerate(case["turns"], start=1):
                has_signal = has_signal or bool(turn["use_signal"])
                actual = (
                    "safety_boundary"
                    if assess_high_risk_question(turn["question"])
                    else fallback_plan(turn["question"], has_signal=has_signal)["intent"]
                )
                if actual != turn["expected_intent"]:
                    mismatches.append((case["id"], turn_index, actual))
        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main()
