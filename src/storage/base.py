from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

from langchain_core.documents import Document


@dataclass(frozen=True)
class EmbeddedChunk:
    """Stored RFC chunk with a precomputed embedding."""

    rfc_id: str
    chunk_index: int
    source: str
    content: str
    embedding: list[float]


class KnowledgeStore(ABC):
    """Abstract RFC knowledge store."""

    @abstractmethod
    def add_documents(self, documents: Sequence[Document]) -> None:
        """Persist RFC documents and make them searchable."""

    @abstractmethod
    def similarity_search(self, query: str, k: int = 5) -> list[Document]:
        """Return the most relevant RFC chunks for a query."""

    @abstractmethod
    def has_rfc(self, rfc_id: str) -> bool:
        """Check whether an RFC is already indexed."""

    def upsert_embedded_chunks(self, chunks: Sequence[EmbeddedChunk]) -> None:
        """Persist precomputed embeddings when a backend supports it."""
        raise NotImplementedError("This backend does not accept precomputed embeddings.")
