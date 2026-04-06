import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import HumanMessage

# Set dummy env vars BEFORE importing anything from src.
os.environ["OPENROUTER_API_KEY"] = "dummy_key"
os.environ["DEFAULT_MODEL"] = "dummy_model"
os.environ["ENABLE_LANGSMITH_TRACING"] = "false"

# Add project root to path.
sys.path.append(os.getcwd())

from src.agents.rfc_agent import analyze, check_availability, search


class TestRFCAgent(unittest.IsolatedAsyncioTestCase):
    @patch("src.agents.rfc_agent._build_search_query", return_value="IGMPv3 query interval")
    def test_analyze_supported_protocol_routes_to_availability_check(self, mock_query_builder):
        state = {"messages": [HumanMessage(content="IGMPv3 的默认查询间隔是多少？")]}

        result = analyze(state)

        self.assertEqual(result["target_rfc_ids"], ["3376"])
        self.assertEqual(result["query"], "IGMPv3 query interval")
        self.assertEqual(result["next_step"], "check_availability")
        mock_query_builder.assert_called_once()

    @patch("src.agents.rfc_agent._build_search_query", return_value="PIM join prune interval default")
    def test_analyze_supports_protocol_name_followed_by_chinese_text(self, mock_query_builder):
        state = {"messages": [HumanMessage(content="PIM协议中join prune interval的默认值是多少？")]}

        result = analyze(state)

        self.assertEqual(result["target_rfc_ids"], ["7761"])
        self.assertEqual(result["query"], "PIM join prune interval default")
        self.assertEqual(result["next_step"], "check_availability")
        mock_query_builder.assert_called_once()

    @patch("src.agents.rfc_agent._build_search_query")
    def test_analyze_old_version_returns_not_ingested(self, mock_query_builder):
        state = {"messages": [HumanMessage(content="IGMPv2 支持吗？")]}

        result = analyze(state)

        self.assertEqual(result["availability_status"], "not_ingested")
        self.assertEqual(result["next_step"], "answer_not_ingested")
        mock_query_builder.assert_not_called()

    @patch("src.agents.rfc_agent._build_search_query")
    def test_analyze_old_version_followed_by_chinese_text_returns_not_ingested(self, mock_query_builder):
        state = {"messages": [HumanMessage(content="IGMPv2协议支持吗？")]}

        result = analyze(state)

        self.assertEqual(result["availability_status"], "not_ingested")
        self.assertEqual(result["next_step"], "answer_not_ingested")
        mock_query_builder.assert_not_called()

    @patch("src.agents.rfc_agent._build_search_query")
    def test_analyze_unsupported_rfc_returns_not_ingested(self, mock_query_builder):
        state = {"messages": [HumanMessage(content="RFC 8200 defines which IPv6 header fields?")]}

        result = analyze(state)

        self.assertEqual(result["availability_status"], "not_ingested")
        self.assertEqual(result["next_step"], "answer_not_ingested")
        mock_query_builder.assert_not_called()

    async def test_check_availability_routes_to_search_when_preloaded(self):
        with patch("src.agents.rfc_agent.get_missing_rfc_ids", AsyncMock(return_value=[])):
            result = await check_availability({"target_rfc_ids": ["3376"]})

        self.assertEqual(result["availability_status"], "ready")
        self.assertEqual(result["next_step"], "search")

    async def test_check_availability_returns_not_ingested_when_missing(self):
        with patch(
            "src.agents.rfc_agent.get_missing_rfc_ids",
            AsyncMock(return_value=["3810"]),
        ):
            result = await check_availability({"target_rfc_ids": ["3810"]})

        self.assertEqual(result["availability_status"], "not_ingested")
        self.assertEqual(result["next_step"], "answer_not_ingested")
        self.assertIn("暂未入库", result["availability_message"])

    async def test_search_limits_query_to_target_rfc_ids(self):
        with patch("src.agents.rfc_agent.search_rfc_knowledge", AsyncMock(return_value="RFC Content")) as mock_search:
            state = {"query": "IGMPv3 query interval", "target_rfc_ids": ["3376"]}
            result = await search(state)

        self.assertEqual(result["context"], "RFC Content")
        self.assertEqual(result["next_step"], "answer")
        mock_search.assert_awaited_once_with("IGMPv3 query interval", ["3376"])


if __name__ == "__main__":
    unittest.main()
