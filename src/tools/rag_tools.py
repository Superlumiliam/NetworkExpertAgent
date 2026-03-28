from typing import List
from langchain_core.documents import Document
from src.storage.factory import get_knowledge_store

def add_documents(documents: List[Document]) -> None:
    """Add documents to the vector store."""
    get_knowledge_store().add_documents(documents)

def query_knowledge_base(query: str, n_results: int = 5) -> List[Document]:
    """Query the vector database for relevant documents."""
    return get_knowledge_store().similarity_search(query, k=n_results)

def check_rfc_exists(rfc_id: str) -> bool:
    """Check if an RFC is already indexed in the vector store."""
    return get_knowledge_store().has_rfc(rfc_id)
