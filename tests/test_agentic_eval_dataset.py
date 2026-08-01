from __future__ import annotations

import hashlib
import re
import tempfile
import unittest
from collections import Counter
from dataclasses import replace
from pathlib import Path

from equipdoc_agent.agent.knowledge_answer import (
    build_ranked_evidence_candidates,
    render_structured_evidence_answer,
    select_evidence_for_question,
)
from equipdoc_agent.agent.planning import fallback_plan
from equipdoc_agent.agent.safety import assess_high_risk_question
from equipdoc_agent.config import Settings
from equipdoc_agent.rag import KnowledgeRetriever
from scripts.eval_agentic_full import _load_jsonl, _validate_cases


ROOT = Path(__file__).resolve().parents[1]
FORMAL_EVAL = ROOT / "data/eval/agentic_eval.jsonl"
SMOKE_EVAL = ROOT / "data/eval/agentic_smoke.jsonl"
FORMAL_EVAL_SHA256 = "7f7613ad09819300dbc6edbb98e9d2383d774a3f0cbfee4c939573392dbb23b8"


class AgenticFormalEvalDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = _load_jsonl(FORMAL_EVAL)
        cls.smoke_cases = _load_jsonl(SMOKE_EVAL)

    def test_schema_and_identifiers_are_frozen(self):
        _validate_cases(self.cases)
        self.assertEqual(len(self.cases), 56)
        self.assertEqual(
            [case["id"] for case in self.cases],
            [f"formal_{index:03d}" for index in range(1, 57)],
        )
        self.assertEqual(sum(len(case["turns"]) for case in self.cases), 64)

    def test_formal_dataset_content_hash_is_frozen(self):
        digest = hashlib.sha256(FORMAL_EVAL.read_bytes()).hexdigest()
        self.assertEqual(digest, FORMAL_EVAL_SHA256)

    def test_group_distribution_matches_the_formal_contract(self):
        counts = Counter(case["group"] for case in self.cases)
        self.assertEqual(
            counts,
            {
                "knowledge_qa": 10,
                "cross_equipment": 8,
                "signal_inspection": 6,
                "clarification": 6,
                "safety_boundary": 12,
                "diagnosis": 6,
                "diagnosis_and_memory": 8,
            },
        )
        single_turn_tool_cases = sum(
            len(case["turns"]) == 1
            and case["group"]
            in {"knowledge_qa", "cross_equipment", "signal_inspection", "diagnosis"}
            for case in self.cases
        )
        safety_and_clarification = sum(
            case["group"] in {"safety_boundary", "clarification"} for case in self.cases
        )
        memory_cases = [case for case in self.cases if case["group"] == "diagnosis_and_memory"]
        diagnosis_chains = sum(
            case["group"] in {"diagnosis", "diagnosis_and_memory"} for case in self.cases
        )
        self.assertEqual(single_turn_tool_cases, 30)
        self.assertEqual(safety_and_clarification, 18)
        self.assertEqual(len(memory_cases), 8)
        self.assertTrue(all(len(case["turns"]) == 2 for case in memory_cases))
        self.assertEqual(diagnosis_chains, 14)

    def test_every_turn_has_an_explicit_evaluation_contract(self):
        required_fields = {
            "question",
            "use_signal",
            "expected_intent",
            "expected_tools",
            "allowed_tools",
            "review",
            "required_keywords",
            "require_citation",
        }
        turns = [turn for case in self.cases for turn in case["turns"]]
        self.assertTrue(all(required_fields.issubset(turn) for turn in turns))
        self.assertEqual(sum(turn["review"] == "approve" for turn in turns), 12)
        self.assertEqual(sum(turn["review"] == "reject" for turn in turns), 2)
        self.assertEqual(sum(bool(turn["require_citation"]) for turn in turns), 38)
        self.assertEqual(sum(bool(turn["use_signal"]) for turn in turns), 20)

    def test_formal_questions_do_not_copy_smoke_questions(self):
        smoke_questions = {turn["question"] for case in self.smoke_cases for turn in case["turns"]}
        formal_questions = [turn["question"] for case in self.cases for turn in case["turns"]]
        self.assertEqual(len(formal_questions), len(set(formal_questions)))
        self.assertTrue(smoke_questions.isdisjoint(formal_questions))

    def test_expected_intents_also_match_the_safe_fallback_contract(self):
        mismatches = []
        for case in self.cases:
            has_signal = False
            for turn_index, turn in enumerate(case["turns"], start=1):
                has_signal = has_signal or bool(turn["use_signal"])
                safety = assess_high_risk_question(turn["question"])
                actual_intent = (
                    "safety_boundary"
                    if safety is not None
                    else fallback_plan(
                        turn["question"],
                        has_signal=has_signal,
                    )["intent"]
                )
                if actual_intent != turn["expected_intent"]:
                    mismatches.append(
                        (
                            case["id"],
                            turn_index,
                            turn["expected_intent"],
                            actual_intent,
                        )
                    )
        self.assertEqual(mismatches, [])

    def test_lexical_retrieval_covers_required_slots_for_all_citation_turns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = replace(
                Settings.from_env(ROOT),
                rag_db_dir=Path(temp_dir) / "no-vector-index",
            )
            retriever = KnowledgeRetriever(settings)
            failures = []
            for case in self.cases:
                for turn_index, turn in enumerate(case["turns"], start=1):
                    if not turn["require_citation"]:
                        continue
                    hits = retriever.search(turn["question"], top_k=5)
                    candidates = build_ranked_evidence_candidates(turn["question"], hits)
                    selection = select_evidence_for_question(turn["question"], candidates)
                    if not selection["valid"]:
                        failures.append((case["id"], turn_index, selection["missing_slots"]))
        self.assertEqual(failures, [])

    def test_single_turn_structured_answers_cover_frozen_keywords(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = replace(
                Settings.from_env(ROOT),
                rag_db_dir=Path(temp_dir) / "no-vector-index",
            )
            retriever = KnowledgeRetriever(settings)
            failures = []
            for case in self.cases:
                for turn_index, turn in enumerate(case["turns"], start=1):
                    if not turn["require_citation"] or turn.get("use_signal"):
                        continue
                    if turn_index > 1:
                        # Later turns can depend on the real diagnosis stored in
                        # session memory, which this lexical-only test does not run.
                        continue
                    required_keywords = turn.get("required_keywords", [])
                    hits = retriever.search(turn["question"], top_k=5)
                    candidates = build_ranked_evidence_candidates(turn["question"], hits)
                    selection = select_evidence_for_question(turn["question"], candidates)
                    answer = render_structured_evidence_answer(
                        turn["question"],
                        candidates,
                        selection["selected_ids"],
                        selection["slot_assignments"],
                    )
                    missing = [keyword for keyword in required_keywords if keyword not in answer]
                    if missing:
                        failures.append((case["id"], turn_index, missing))
        self.assertEqual(failures, [])

    def test_dataset_contains_no_private_paths_or_credentials(self):
        raw = FORMAL_EVAL.read_text(encoding="utf-8")
        self.assertNotIn("/root/", raw)
        self.assertNotRegex(raw, re.compile(r"\b[A-Za-z]:[\\/]"))
        self.assertNotIn("signal_path", raw)
        self.assertNotRegex(raw.lower(), re.compile(r"api[_-]?key|bearer\s+\S+"))


if __name__ == "__main__":
    unittest.main()
