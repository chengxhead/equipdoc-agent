import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

from equipdoc_agent.agent import build_graph
from equipdoc_agent.config import Settings


ROOT = Path(__file__).resolve().parents[1]


class FullRagGraphTests(unittest.TestCase):
    def test_full_knowledge_question_sends_retrieved_evidence_to_llm(self):
        settings = replace(
            Settings.from_env(ROOT),
            demo_mode=False,
            rag_db_dir=(ROOT / "runtime/test_full_no_vector_db").resolve(),
        )
        with patch("equipdoc_agent.agent.graph.ChatOpenAI") as chat_class:
            llm = chat_class.return_value
            llm.invoke.return_value = AIMessage(
                content=(
                    "外圈故障会产生周期性冲击 "
                    "[bearing_outer_race_fault#bearing_outer_race_fault_c001]"
                )
            )
            graph = build_graph(settings)
            result = graph.invoke(
                {
                    "messages": [HumanMessage(content="轴承外圈故障为什么会产生周期性冲击？")],
                    "signal_path": "",
                },
                config={"configurable": {"thread_id": "test_full_rag"}},
            )

        prompt_messages = llm.invoke.call_args.args[0]
        combined_prompt = "\n".join(str(message.content) for message in prompt_messages)
        self.assertIn("bearing_outer_race_fault#", combined_prompt)
        self.assertIn("检索证据", combined_prompt)
        self.assertIn("周期性冲击", result["messages"][-1].content)


if __name__ == "__main__":
    unittest.main()
