from __future__ import annotations

from typing import Optional

import src.config.settings as cfg
from src.storage.base import KnowledgeStore
from src.storage.chroma_store import ChromaKnowledgeStore
from src.storage.pgvector_store import PgVectorKnowledgeStore


_store: Optional[KnowledgeStore] = None


def get_knowledge_store() -> KnowledgeStore:
    """Return the configured knowledge store backend."""
    global _store
    if _store is None:
        if cfg.VECTOR_BACKEND == "pgvector":
            _store = PgVectorKnowledgeStore()
        else:
            _store = ChromaKnowledgeStore()
    return _store


def reset_knowledge_store() -> None:
    """Clear the cached backend for tests."""
    global _store
    _store = None
