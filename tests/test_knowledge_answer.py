import unittest

from equipdoc_agent.agent.knowledge_answer import (
    build_full_rag_messages,
    extract_citations,
    render_retrieval_context,
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


if __name__ == "__main__":
    unittest.main()
