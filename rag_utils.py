import os
import sys
import httpx
import asyncio
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
# Switch from OpenAIEmbeddings to HuggingFaceEmbeddings to remove OpenAI dependency
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
import config.settings as cfg

def get_embeddings():
    """Initialize HuggingFace Embeddings (runs locally, no API key needed)."""
    print(f"Loading embedding model: {cfg.EMBEDDING_MODEL_NAME}...", file=sys.stderr)
    return HuggingFaceEmbeddings(model_name=cfg.EMBEDDING_MODEL_NAME)

def get_vector_store():
    """Initialize or load the Chroma vector store."""
    embedding_function = get_embeddings()
    # Ensure directory exists
    os.makedirs(cfg.CHROMA_PATH, exist_ok=True)
    return Chroma(
        persist_directory=cfg.CHROMA_PATH,
        embedding_function=embedding_function,
        collection_name="rfc_knowledge_base"
    )

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

async def add_rfc_to_knowledge_base(rfc_id: str) -> str:
    """Download, chunk, and store RFC in the vector database."""
    try:
        text = await download_rfc_text(rfc_id)
        
        # CPU-bound tasks in thread pool
        chunks = await asyncio.to_thread(chunk_text, text, rfc_id)
        
        # IO-bound (disk) task in thread pool
        def store():
            db = get_vector_store()
            db.add_documents(chunks)
            
        await asyncio.to_thread(store)
        
        return f"Successfully added RFC {rfc_id} to knowledge base. ({len(chunks)} chunks)"
    except Exception as e:
        return f"Error adding RFC {rfc_id}: {str(e)}"

async def query_rfc_knowledge_base(query: str, n_results: int = 25) -> List[str]:
    """Query the vector database for relevant context."""
    try:
        def search():
            db = get_vector_store()
            results = db.similarity_search(query, k=n_results)
            return results
            
        results = await asyncio.to_thread(search)
        
        context_list = []
        for doc in results:
            context_list.append(f"[Source: {doc.metadata.get('source', 'Unknown')}]\n{doc.page_content}")
            
        return context_list
    except Exception as e:
        return [f"Error querying knowledge base: {str(e)}"]
