from __future__ import annotations

import sys

import chromadb

import src.config.settings as cfg
from src.storage.base import EmbeddedChunk
from src.storage.pgvector_store import PgVectorKnowledgeStore


def main() -> None:
    if not cfg.CHROMA_PATH:
        raise ValueError("CHROMA_PATH is not configured.")

    if not cfg.DATABASE_URL:
        raise ValueError("DATABASE_URL must be set before seeding pgvector.")

    client = chromadb.PersistentClient(path=cfg.CHROMA_PATH)
    collection = client.get_collection("rfc_knowledge_base")
    payload = collection.get(include=["documents", "metadatas", "embeddings"])

    documents = payload.get("documents", [])
    metadatas = payload.get("metadatas", [])
    embeddings = payload.get("embeddings", [])

    chunks: list[EmbeddedChunk] = []
    for index, (content, metadata, embedding) in enumerate(zip(documents, metadatas, embeddings)):
        if embedding is None:
            continue

        metadata = metadata or {}
        rfc_id = str(metadata.get("rfc_id", "")).strip()
        if not rfc_id:
            continue

        chunk_index = int(metadata.get("chunk_index", index))
        source = str(metadata.get("source", f"RFC {rfc_id}"))
        chunks.append(
            EmbeddedChunk(
                rfc_id=rfc_id,
                chunk_index=chunk_index,
                source=source,
                content=content,
                embedding=list(embedding),
            )
        )

    store = PgVectorKnowledgeStore()
    store.upsert_embedded_chunks(chunks)
    print(f"Seeded {len(chunks)} RFC chunks from Chroma into pgvector.", file=sys.stderr)


if __name__ == "__main__":
    main()
