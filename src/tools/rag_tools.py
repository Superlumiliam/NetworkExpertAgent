import os
import sys
from typing import List, Optional
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import src.config.settings as cfg

_vector_store: Optional[Chroma] = None
_embeddings: Optional[HuggingFaceEmbeddings] = None

def get_embeddings() -> HuggingFaceEmbeddings:
    """Initialize HuggingFace Embeddings (runs locally, no API key needed)."""
    global _embeddings
    if _embeddings is None:
        print(f"Loading embedding model: {cfg.EMBEDDING_MODEL_NAME}...", file=sys.stderr)
        _embeddings = HuggingFaceEmbeddings(model_name=cfg.EMBEDDING_MODEL_NAME)
    return _embeddings

def get_vector_store() -> Chroma:
    """Initialize or load the Chroma vector store."""
    global _vector_store
    if _vector_store is None:
        embedding_function = get_embeddings()
        # Ensure directory exists
        os.makedirs(cfg.CHROMA_PATH, exist_ok=True)
        _vector_store = Chroma(
            persist_directory=cfg.CHROMA_PATH,
            embedding_function=embedding_function,
            collection_name="rfc_knowledge_base"
        )
    return _vector_store

def add_documents(documents: List[Document]) -> None:
    """Add documents to the vector store."""
    db = get_vector_store()
    db.add_documents(documents)

def query_knowledge_base(query: str, n_results: int = 5) -> List[Document]:
    """Query the vector database for relevant documents."""
    db = get_vector_store()
    results = db.similarity_search(query, k=n_results)
    return results

def check_rfc_exists(rfc_id: str) -> bool:
    """Check if an RFC is already indexed in the vector store."""
    db = get_vector_store()
    # Simple check: search for metadata
    # Chroma doesn't have a direct "exists" check for metadata easily without a query,
    # but we can filter.
    results = db.get(where={"rfc_id": rfc_id}, limit=1)
    return len(results['ids']) > 0
