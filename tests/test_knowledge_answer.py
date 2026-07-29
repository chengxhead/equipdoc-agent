import unittest

from equipdoc_agent.agent.knowledge_answer import (
    build_citation_retry_messages,
    build_full_rag_messages,
    extract_citations,
    render_extractive_fallback,
    render_retrieval_context,
    validate_answer_citations,
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

    def test_full_prompt_requires_exact_citation_format(self):
        messages = build_full_rag_messages("外圈故障有什么特征？", self.hits)
        combined = "\n".join(str(message.content) for message in messages)
        self.assertIn("doc_id#chunk_id", combined)
        self.assertIn("不得编造", combined)

    def test_extracts_full_citations_and_ignores_numeric_markers(self):
        citations = extract_citations(
            "外圈故障会产生冲击 [bearing_outer_race_fault#bearing_outer_race_fault_c001] [1]"
        )
        self.assertEqual(
            citations,
            [("bearing_outer_race_fault", "bearing_outer_race_fault_c001")],
        )

    def test_retry_prompt_lists_only_allowed_full_ids(self):
        messages = build_citation_retry_messages("问题", self.hits, "没有引用的草稿")
        combined = "\n".join(str(message.content) for message in messages)
        self.assertIn("唯一允许使用的引用ID", combined)
        self.assertIn("bearing_outer_race_fault#bearing_outer_race_fault_c001", combined)

    def test_invalid_answer_falls_back_to_exact_cited_evidence(self):
        validation = validate_answer_citations("没有引用", self.hits)
        self.assertFalse(validation["valid"])
        fallback = render_extractive_fallback(self.hits)
        self.assertTrue(validate_answer_citations(fallback, self.hits)["valid"])
        self.assertIn("系统已隐藏未验证草稿", fallback)

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
            "- 冲击呈现稳定重复模式 "
            "[bearing_outer_race_fault#bearing_outer_race_fault_c001]"
        )
        validation = validate_answer_citations(answer, self.hits)
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["claim_citation_coverage"], 1.0)


if __name__ == "__main__":
    unittest.main()
