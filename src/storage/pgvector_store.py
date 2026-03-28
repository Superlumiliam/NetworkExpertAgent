from __future__ import annotations

import uuid
from typing import Iterable, Sequence

import psycopg
from langchain_core.documents import Document
from pgvector import Vector
from pgvector.psycopg import register_vector

import src.config.settings as cfg
from src.storage.base import EmbeddedChunk, KnowledgeStore
from src.storage.embeddings import get_embeddings


def _stable_chunk_id(rfc_id: str, chunk_index: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"rfc:{rfc_id}:{chunk_index}")


class PgVectorKnowledgeStore(KnowledgeStore):
    """Managed Postgres + pgvector backend for production deployments."""

    def __init__(self) -> None:
        self._schema_ready = False

    def _connect(self) -> psycopg.Connection:
        database_url = cfg.get_database_url()
        if not database_url:
            raise ValueError("DATABASE_URL is required when VECTOR_BACKEND=pgvector.")

        conn = psycopg.connect(database_url)
        register_vector(conn)
        if not self._schema_ready:
            self._ensure_schema(conn)
            self._schema_ready = True
        return conn

    def _ensure_schema(self, conn: psycopg.Connection) -> None:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rfc_chunks (
                    id UUID PRIMARY KEY,
                    rfc_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding VECTOR(384) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (rfc_id, chunk_index)
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rfc_chunks_rfc_id
                ON rfc_chunks (rfc_id)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rfc_chunks_embedding_cosine
                ON rfc_chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
                """
            )
        conn.commit()

    def add_documents(self, documents: Sequence[Document]) -> None:
        docs = list(documents)
        if not docs:
            return

        texts = [doc.page_content for doc in docs]
        embeddings = get_embeddings().embed_documents(texts)
        chunks = [
            EmbeddedChunk(
                rfc_id=str(doc.metadata.get("rfc_id", "")),
                chunk_index=int(doc.metadata.get("chunk_index", index)),
                source=str(doc.metadata.get("source", "Unknown")),
                content=doc.page_content,
                embedding=list(embedding),
            )
            for index, (doc, embedding) in enumerate(zip(docs, embeddings))
        ]
        self.upsert_embedded_chunks(chunks)

    def upsert_embedded_chunks(self, chunks: Sequence[EmbeddedChunk]) -> None:
        chunk_list = list(chunks)
        if not chunk_list:
            return

        rows = [
            (
                _stable_chunk_id(chunk.rfc_id, chunk.chunk_index),
                chunk.rfc_id,
                chunk.chunk_index,
                chunk.source,
                chunk.content,
                Vector(chunk.embedding),
            )
            for chunk in chunk_list
        ]

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO rfc_chunks (id, rfc_id, chunk_index, source, content, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (rfc_id, chunk_index) DO UPDATE SET
                        source = EXCLUDED.source,
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding
                    """,
                    rows,
                )
            conn.commit()

    def similarity_search(self, query: str, k: int = 5) -> list[Document]:
        query_embedding = Vector(get_embeddings().embed_query(query))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source, content, rfc_id, chunk_index
                    FROM rfc_chunks
                    ORDER BY embedding <=> %s
                    LIMIT %s
                    """,
                    (query_embedding, k),
                )
                rows = cur.fetchall()

        return [
            Document(
                page_content=content,
                metadata={"source": source, "rfc_id": rfc_id, "chunk_index": chunk_index},
            )
            for source, content, rfc_id, chunk_index in rows
        ]

    def has_rfc(self, rfc_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM rfc_chunks WHERE rfc_id = %s)",
                    (rfc_id,),
                )
                row = cur.fetchone()
        return bool(row and row[0])
