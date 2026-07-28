import unittest
from dataclasses import replace
from pathlib import Path

from equipdoc_agent.config import Settings
from equipdoc_agent.rag import KnowledgeRetriever


ROOT = Path(__file__).resolve().parents[1]


class RetrieverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        settings = replace(
            Settings.from_env(ROOT),
            rag_db_dir=(ROOT / "runtime/test_no_vector_db").resolve(),
        )
        cls.retriever = KnowledgeRetriever(settings)

    def assert_doc_recalled(self, query, expected_doc_id, top_k=5):
        doc_ids = [item["doc_id"] for item in self.retriever.search(query, top_k=top_k)]
        self.assertIn(expected_doc_id, doc_ids)

    def test_retrieves_gearbox_wear_notes(self):
        self.assert_doc_recalled("齿轮箱齿面磨损有哪些信号特征", "pump_gearbox_faults")

    def test_retrieves_pump_cavitation_notes(self):
        self.assert_doc_recalled("泵发生汽蚀有什么表现", "pump_gearbox_faults")

    def test_retrieves_outer_race_notes(self):
        self.assert_doc_recalled("轴承外圈故障的振动和包络谱特征", "bearing_outer_race_fault")


if __name__ == "__main__":
    unittest.main()
