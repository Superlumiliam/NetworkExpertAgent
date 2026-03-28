import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

# Set dummy env vars BEFORE importing anything from src
os.environ["OPENROUTER_API_KEY"] = "dummy_key"
os.environ["DEFAULT_MODEL"] = "dummy_model"
os.environ["ENABLE_LANGSMITH_TRACING"] = "false"

# Add project root to path
sys.path.append(os.getcwd())

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda

from src.agents.rfc_agent import RFCExpertAgentRuntime, rfc_agent


class TestRFCAgent(unittest.IsolatedAsyncioTestCase):
    async def test_existing_rfc_skips_download(self):
        runtime = RFCExpertAgentRuntime()
        runtime._run_intent = AsyncMock(return_value={"request_type": "specific_rfc"})
        runtime._run_planning = AsyncMock(
            return_value={
                "rfc_id": "7540",
                "query": "HTTP/2 frame header",
                "needs_rfc_content": True,
                "should_check_local": True,
            }
        )
        runtime._run_answer = AsyncMock(return_value="RFC-backed answer")

        mock_check = AsyncMock(return_value=True)
        mock_add = AsyncMock(return_value="should not run")
        mock_search = AsyncMock(return_value="RFC Content")

        with patch("src.agents.rfc_agent.check_rfc_status", new=SimpleNamespace(ainvoke=mock_check)), patch(
            "src.agents.rfc_agent.add_rfc", new=SimpleNamespace(ainvoke=mock_add)
        ), patch("src.agents.rfc_agent.search_rfc_knowledge", new=SimpleNamespace(ainvoke=mock_search)):
            result = await runtime.ainvoke({"messages": [HumanMessage(content="What does RFC 7540 say?")]})

        mock_check.assert_awaited_once_with("7540")
        mock_add.assert_not_awaited()
        mock_search.assert_awaited_once_with("HTTP/2 frame header")
        self.assertEqual(result["messages"][-1].content, "RFC-backed answer")
        self.assertEqual(result["context"], "RFC Content")

    async def test_missing_rfc_downloads_then_searches(self):
        runtime = RFCExpertAgentRuntime()
        runtime._run_intent = AsyncMock(return_value={"request_type": "specific_rfc"})
        runtime._run_planning = AsyncMock(
            return_value={
                "rfc_id": "3376",
                "query": "IGMPv3 Query Interval default value",
                "needs_rfc_content": True,
                "should_check_local": True,
            }
        )
        runtime._run_answer = AsyncMock(return_value="Downloaded and answered")

        mock_check = AsyncMock(return_value=False)
        mock_add = AsyncMock(return_value="Successfully added RFC 3376")
        mock_search = AsyncMock(return_value="RFC 3376 says 125 seconds")

        with patch("src.agents.rfc_agent.check_rfc_status", new=SimpleNamespace(ainvoke=mock_check)), patch(
            "src.agents.rfc_agent.add_rfc", new=SimpleNamespace(ainvoke=mock_add)
        ), patch("src.agents.rfc_agent.search_rfc_knowledge", new=SimpleNamespace(ainvoke=mock_search)):
            result = await runtime.ainvoke({"messages": [HumanMessage(content="IGMPv3 query interval default?")]})

        mock_check.assert_awaited_once_with("3376")
        mock_add.assert_awaited_once_with("3376")
        mock_search.assert_awaited_once_with("IGMPv3 Query Interval default value")
        self.assertEqual(result["context"], "RFC 3376 says 125 seconds")

    async def test_protocol_topic_searches_without_download(self):
        runtime = RFCExpertAgentRuntime()
        runtime._run_intent = AsyncMock(return_value={"request_type": "technical_detail"})
        runtime._run_planning = AsyncMock(
            return_value={
                "rfc_id": None,
                "query": "OSPFv3 LSA aging behavior",
                "needs_rfc_content": False,
                "should_check_local": False,
            }
        )
        runtime._run_answer = AsyncMock(return_value="Search-only answer")

        mock_check = AsyncMock(return_value=False)
        mock_add = AsyncMock(return_value="should not run")
        mock_search = AsyncMock(return_value="OSPFv3 content")

        with patch("src.agents.rfc_agent.check_rfc_status", new=SimpleNamespace(ainvoke=mock_check)), patch(
            "src.agents.rfc_agent.add_rfc", new=SimpleNamespace(ainvoke=mock_add)
        ), patch("src.agents.rfc_agent.search_rfc_knowledge", new=SimpleNamespace(ainvoke=mock_search)):
            result = await runtime.ainvoke({"messages": [HumanMessage(content="How does OSPFv3 age LSAs?")]})

        mock_check.assert_not_awaited()
        mock_add.assert_not_awaited()
        mock_search.assert_awaited_once_with("OSPFv3 LSA aging behavior")
        self.assertEqual(result["context"], "OSPFv3 content")

    async def test_download_failure_goes_to_conservative_answer(self):
        runtime = RFCExpertAgentRuntime()
        runtime._run_intent = AsyncMock(return_value={"request_type": "specific_rfc"})
        runtime._run_planning = AsyncMock(
            return_value={
                "rfc_id": "8200",
                "query": "IPv6 Hop Limit field",
                "needs_rfc_content": True,
                "should_check_local": True,
            }
        )
        runtime._run_answer = AsyncMock(return_value="I could not confirm this from RFC context.")

        mock_check = AsyncMock(return_value=False)
        mock_add = AsyncMock(return_value="Error adding RFC 8200: timeout")
        mock_search = AsyncMock(return_value="should not run")

        with patch("src.agents.rfc_agent.check_rfc_status", new=SimpleNamespace(ainvoke=mock_check)), patch(
            "src.agents.rfc_agent.add_rfc", new=SimpleNamespace(ainvoke=mock_add)
        ), patch("src.agents.rfc_agent.search_rfc_knowledge", new=SimpleNamespace(ainvoke=mock_search)):
            result = await runtime.ainvoke({"messages": [HumanMessage(content="What does RFC 8200 say about Hop Limit?")]})

        mock_search.assert_not_awaited()
        self.assertEqual(result["context"], "")
        self.assertEqual(result["messages"][-1].content, "I could not confirm this from RFC context.")

    async def test_empty_search_result_is_reported(self):
        runtime = RFCExpertAgentRuntime()
        runtime._run_intent = AsyncMock(return_value={"request_type": "technical_detail"})
        runtime._run_planning = AsyncMock(
            return_value={
                "rfc_id": None,
                "query": "Made up protocol field",
                "needs_rfc_content": False,
                "should_check_local": False,
            }
        )
        runtime._run_answer = AsyncMock(return_value="No RFC evidence found in the local knowledge base.")

        mock_search = AsyncMock(return_value="No relevant information found in the knowledge base.")

        with patch("src.agents.rfc_agent.search_rfc_knowledge", new=SimpleNamespace(ainvoke=mock_search)):
            result = await runtime.ainvoke({"messages": [HumanMessage(content="What is the made up protocol field?")]})

        self.assertEqual(result["context"], "")
        self.assertEqual(result["messages"][-1].content, "No RFC evidence found in the local knowledge base.")

    def test_skill_loader_is_progressive(self):
        runtime = RFCExpertAgentRuntime()

        runtime.skill_loader.load("skill", "base", "intent")
        self.assertEqual(runtime.skill_loader.load_history, ["skill", "base", "intent"])

        runtime.skill_loader.load("planning")
        self.assertEqual(runtime.skill_loader.load_history, ["skill", "base", "intent", "planning"])

        runtime.skill_loader.load("answering")
        self.assertEqual(runtime.skill_loader.load_history, ["skill", "base", "intent", "planning", "answering"])
        self.assertNotIn("retrieval", runtime.skill_loader.load_history)

    async def test_planning_handles_intent_dict_without_prompt_key_error(self):
        runtime = RFCExpertAgentRuntime()
        runtime.llm = RunnableLambda(
            lambda _: '{"rfc_id": "3376", "query": "IGMPv3 Query Interval default value", "needs_rfc_content": true, "should_check_local": true, "answer_strategy": "rfc-backed"}'
        )

        result = await runtime._run_planning(
            "IGMPv3 query interval default?",
            {"request_type": "technical_detail", "topic": "IGMPv3"},
        )

        self.assertEqual(result["rfc_id"], "3376")
        self.assertEqual(result["query"], "IGMPv3 Query Interval default value")

    async def test_planning_parses_minimax_tool_call_fallback(self):
        runtime = RFCExpertAgentRuntime()
        runtime.llm = RunnableLambda(
            lambda _: """<minimax:tool_call>
<invoke name="search_rfc_knowledge">
<parameter name="query">IGMPv3 TO_EX state transition INCLUDE to EXCLUDE mode router state</parameter>
</invoke>
</minimax:tool_call>"""
        )

        result = await runtime._run_planning(
            "IGMPv3中TO_EX状态转换的条件是什么？",
            {"request_type": "technical_detail", "mentions_rfc": False},
        )

        self.assertEqual(
            result["query"],
            "IGMPv3 TO_EX state transition INCLUDE to EXCLUDE mode router state",
        )
        self.assertIsNone(result["rfc_id"])
        self.assertFalse(result["should_check_local"])

class TestExportedRuntime(unittest.IsolatedAsyncioTestCase):
    async def test_exported_rfc_agent_keeps_ainvoke_contract(self):
        with patch.object(rfc_agent, "_run_intent", new=AsyncMock(return_value={"request_type": "specific_rfc"})), patch.object(
            rfc_agent,
            "_run_planning",
            new=AsyncMock(
                return_value={
                    "rfc_id": "791",
                    "query": "IPv4 header format",
                    "needs_rfc_content": False,
                    "should_check_local": False,
                }
            ),
        ), patch.object(
            rfc_agent, "_run_retrieval", new=AsyncMock(return_value={"context": "IPv4 context", "retrieval_notes": ""})
        ), patch.object(rfc_agent, "_run_answer", new=AsyncMock(return_value="IPv4 answer")):
            result = await rfc_agent.ainvoke({"messages": [HumanMessage(content="Tell me about RFC 791")]})

        self.assertEqual(result["messages"][-1].content, "IPv4 answer")
        self.assertEqual(result["rfc_id"], "791")
        self.assertEqual(result["query"], "IPv4 header format")


if __name__ == "__main__":
    unittest.main()
