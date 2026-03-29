import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import asyncio

# Set dummy env vars BEFORE importing anything from src
os.environ["OPENROUTER_API_KEY"] = "dummy_key"
os.environ["DEFAULT_MODEL"] = "dummy_model"
os.environ["ENABLE_LANGSMITH_TRACING"] = "false"

# Add project root to path
sys.path.append(os.getcwd())

from src.core.router import route_question
from src.agents.rfc_agent import check_local, search, download
from src.agents.general_agent import general_chat
from langchain_core.messages import HumanMessage, AIMessage

class TestRFCAgent(unittest.IsolatedAsyncioTestCase):
    
    async def test_check_local(self):
        # Patch the entire tool object in the module where it is used
        with patch("src.agents.rfc_agent.check_rfc_status") as mock_tool:
            # Mock the invoke method of the tool
            mock_tool.ainvoke = AsyncMock()
            
            mock_tool.ainvoke.return_value = True
            state = {"rfc_id": "7540"}
            result = await check_local(state)
            self.assertEqual(result["next_step"], "search")
            
            mock_tool.ainvoke.return_value = False
            result = await check_local(state)
            self.assertEqual(result["next_step"], "download")

    async def test_search(self):
        with patch("src.agents.rfc_agent.search_rfc_knowledge") as mock_tool:
            mock_tool.ainvoke = AsyncMock()
            mock_tool.ainvoke.return_value = "RFC Content"
            
            state = {"query": "http2"}
            result = await search(state)
            self.assertEqual(result["context"], "RFC Content")
            self.assertEqual(result["next_step"], "answer")
            
    async def test_download(self):
        with patch("src.agents.rfc_agent.add_rfc") as mock_tool:
            mock_tool.ainvoke = AsyncMock()
            mock_tool.ainvoke.return_value = "Success"
            
            state = {"rfc_id": "7540"}
            result = await download(state)
            self.assertEqual(result["context"], "Success")
            self.assertEqual(result["next_step"], "search")

if __name__ == "__main__":
    unittest.main()
