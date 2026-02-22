import asyncio
import os
import sys
from mcp.server.fastmcp import FastMCP
from rag_utils import add_rfc_to_knowledge_base, query_rfc_knowledge_base

# Initialize FastMCP server
mcp = FastMCP("RFC Expert")

@mcp.tool()
async def add_rfc(rfc_id: str) -> str:
    """
    Download and index an RFC document into the vector database.
    
    Args:
        rfc_id: The RFC number (e.g., "7540" or "rfc7540").
    """
    return await add_rfc_to_knowledge_base(rfc_id)

@mcp.tool()
async def search_rfc_knowledge(query: str) -> str:
    """
    Search the indexed RFC knowledge base for relevant sections.
    
    Args:
        query: The search query or question about a protocol.
    """
    results = await query_rfc_knowledge_base(query)
    if not results:
        return "No relevant information found in the knowledge base."
    return "\n\n---\n\n".join(results)

if __name__ == "__main__":
    # Ensure API key is set or warn
    # We use local embeddings now, so OPENAI_API_KEY is not strictly required for the server/RAG part.
    # But agent_client needs OPENROUTER_API_KEY.
    
    print("Starting RFC Expert MCP Server...", file=sys.stderr)
    mcp.run()
