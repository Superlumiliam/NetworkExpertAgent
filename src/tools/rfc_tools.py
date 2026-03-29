import httpx
import sys
import asyncio
from typing import List, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.tools import tool

import src.config.settings as cfg
from src.tools.rag_tools import add_documents, query_knowledge_base, check_rfc_exists

async def download_rfc_text(rfc_id: str) -> str:
    """Download RFC text from the official editor asynchronously."""
    # Ensure rfc_id is just the number
    rfc_id = str(rfc_id).lower().replace("rfc", "").strip()
    url = cfg.RFC_BASE_URL.format(rfc_id=rfc_id)
    
    print(f"Downloading RFC {rfc_id} from {url}...", file=sys.stderr)
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to download RFC {rfc_id}. Status code: {response.status_code}")

def chunk_text(text: str, rfc_id: str) -> List[Document]:
    """Split text into chunks for RAG."""
    # RFCs have specific structure (headers, footers, page breaks).
    # A simple recursive splitter is a good start.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    docs = text_splitter.create_documents([text])
    # Add metadata
    for doc in docs:
        doc.metadata = {"source": f"RFC {rfc_id}", "rfc_id": rfc_id}
        
    return docs

@tool
async def add_rfc(rfc_id: str) -> str:
    """
    Download and index an RFC document into the vector database.
    
    Args:
        rfc_id: The RFC number (e.g., "7540" or "rfc7540").
    """
    try:
        rfc_id = str(rfc_id).lower().replace("rfc", "").strip()
        text = await download_rfc_text(rfc_id)
        
        # CPU-bound tasks in thread pool
        chunks = await asyncio.to_thread(chunk_text, text, rfc_id)
        
        # IO-bound (disk) task in thread pool
        await asyncio.to_thread(add_documents, chunks)
        
        return f"Successfully added RFC {rfc_id} to knowledge base. ({len(chunks)} chunks)"
    except Exception as e:
        return f"Error adding RFC {rfc_id}: {str(e)}"

@tool
async def check_rfc_status(rfc_id: str) -> bool:
    """
    Check if an RFC is already indexed in the knowledge base.
    
    Args:
        rfc_id: The RFC number (e.g., "7540" or "rfc7540").
    """
    try:
        # Ensure rfc_id is just the number
        rfc_id = str(rfc_id).lower().replace("rfc", "").strip()
        
        def check():
            return check_rfc_exists(rfc_id)
            
        exists = await asyncio.to_thread(check)
        return exists
    except Exception:
        return False

@tool
async def search_rfc_knowledge(query: str) -> str:
    """
    Search the indexed RFC knowledge base for relevant sections.
    
    Args:
        query: The search query or question about a protocol.
    """
    try:
        def search():
            results = query_knowledge_base(query, n_results=5)
            return results
            
        results = await asyncio.to_thread(search)
        
        if not results:
            return "No relevant information found in the knowledge base."
            
        context_list = []
        for doc in results:
            context_list.append(f"[Source: {doc.metadata.get('source', 'Unknown')}]\n{doc.page_content}")
            
        return "\n\n---\n\n".join(context_list)
    except Exception as e:
        return f"Error querying knowledge base: {str(e)}"
