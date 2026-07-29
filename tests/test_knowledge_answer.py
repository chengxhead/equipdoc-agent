import unittest

from equipdoc_agent.agent.knowledge_answer import (
    build_evidence_candidates,
    build_citation_retry_messages,
    build_full_rag_messages,
    extract_citations,
    extract_evidence_selection,
    render_extractive_fallback,
    render_selected_evidence,
    render_retrieval_context,
    validate_answer_citations,
    validate_evidence_selection,
)


class KnowledgeAnswerTests(unittest.TestCase):
    def setUp(self):
        self.hits = [
            {
                "doc_id": "bearing_outer_race_fault",
                "chunk_id": "bearing_outer_race_fault_c001",
                "text": "外圈缺陷会产生周期性冲击。",
            }
        ]

    def test_context_contains_machine_checkable_citation(self):
        context = render_retrieval_context(self.hits)
        self.assertIn(
            "[bearing_outer_race_fault#bearing_outer_race_fault_c001]",
            context,
        )

    def test_full_prompt_requires_evidence_id_selection(self):
        messages = build_full_rag_messages("外圈故障有什么特征？", self.hits)
        combined = "\n".join(str(message.content) for message in messages)
        self.assertIn("EVIDENCE_IDS", combined)
        self.assertIn("[E01]", combined)

    def test_extracts_full_citations_and_ignores_numeric_markers(self):
        citations = extract_citations(
            "外圈故障会产生冲击 [bearing_outer_race_fault#bearing_outer_race_fault_c001] [1]"
        )
        self.assertEqual(
            citations,
            [("bearing_outer_race_fault", "bearing_outer_race_fault_c001")],
        )

    def test_retry_prompt_lists_only_allowed_evidence_ids(self):
        messages = build_citation_retry_messages("问题", self.hits, "没有ID的输出")
        combined = "\n".join(str(message.content) for message in messages)
        self.assertIn("唯一允许选择的证据句ID", combined)
        self.assertIn("E01", combined)

    def test_extracts_and_validates_evidence_selection(self):
        candidates = build_evidence_candidates(self.hits)
        selected = extract_evidence_selection("EVIDENCE_IDS: E01,E02,E01")
        self.assertEqual(selected, ["E01", "E02"])
        validation = validate_evidence_selection(selected, candidates)
        self.assertFalse(validation["valid"])
        self.assertEqual(validation["unknown_ids"], ["E02"])

    def test_selected_evidence_is_rendered_with_source_citation(self):
        candidates = build_evidence_candidates(self.hits)
        answer = render_selected_evidence(candidates, ["E01"])
        self.assertTrue(validate_answer_citations(answer, self.hits)["valid"])
        self.assertIn("[bearing_outer_race_fault#bearing_outer_race_fault_c001]", answer)

    def test_invalid_answer_falls_back_to_exact_cited_evidence(self):
        validation = validate_answer_citations("没有引用", self.hits)
        self.assertFalse(validation["valid"])
        fallback = render_extractive_fallback(self.hits)
        self.assertTrue(validate_answer_citations(fallback, self.hits)["valid"])
        self.assertIn("系统已隐藏未验证输出", fallback)

    def test_one_trailing_citation_cannot_cover_multiple_sentences(self):
        answer = (
            "外圈缺陷会产生周期性冲击。"
            "每转只重复一次 [bearing_outer_race_fault#bearing_outer_race_fault_c001]"
        )
        validation = validate_answer_citations(answer, self.hits)
        self.assertFalse(validation["valid"])
        self.assertEqual(validation["claim_count"], 2)
        self.assertEqual(validation["cited_claim_count"], 1)
        self.assertEqual(validation["claim_citation_coverage"], 0.5)

    def test_each_claim_with_allowed_citation_is_valid(self):
        answer = (
            "- 外圈缺陷会产生周期性冲击 "
            "[bearing_outer_race_fault#bearing_outer_race_fault_c001]\n"
            "- 外圈缺陷会产生周期性冲击 "
            "[bearing_outer_race_fault#bearing_outer_race_fault_c001]"
        )
        validation = validate_answer_citations(answer, self.hits)
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["claim_citation_coverage"], 1.0)
        self.assertEqual(validation["claim_evidence_match_rate"], 1.0)

    def test_cited_but_unsupported_paraphrase_is_invalid(self):
        answer = (
            "外圈缺陷每转只冲击一次 "
            "[bearing_outer_race_fault#bearing_outer_race_fault_c001]"
        )
        validation = validate_answer_citations(answer, self.hits)
        self.assertFalse(validation["valid"])
        self.assertEqual(validation["claim_citation_coverage"], 1.0)
        self.assertEqual(validation["claim_evidence_match_rate"], 0.0)
        self.assertEqual(len(validation["unsupported_claims"]), 1)


if __name__ == "__main__":
    unittest.main()
