from __future__ import annotations

import os
from typing import Optional, Sequence

from langchain_chroma import Chroma
from langchain_core.documents import Document

import src.config.settings as cfg
from src.storage.base import KnowledgeStore
from src.storage.embeddings import get_embeddings


class ChromaKnowledgeStore(KnowledgeStore):
    """Local Chroma-backed store for development and fallback usage."""

    def __init__(self) -> None:
        self._vector_store: Optional[Chroma] = None

    def _get_vector_store(self) -> Chroma:
        if self._vector_store is None:
            os.makedirs(cfg.CHROMA_PATH, exist_ok=True)
            self._vector_store = Chroma(
                persist_directory=cfg.CHROMA_PATH,
                embedding_function=get_embeddings(),
                collection_name="rfc_knowledge_base",
            )
        return self._vector_store

    def add_documents(self, documents: Sequence[Document]) -> None:
        self._get_vector_store().add_documents(list(documents))

    def similarity_search(self, query: str, k: int = 5) -> list[Document]:
        return self._get_vector_store().similarity_search(query, k=k)

    def has_rfc(self, rfc_id: str) -> bool:
        results = self._get_vector_store().get(where={"rfc_id": rfc_id}, limit=1)
        return len(results["ids"]) > 0
