import asyncio
import sys
from typing import Any, Sequence

import httpx
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import src.config.settings as cfg
from src.core.rfc_catalog import normalize_rfc_id
from src.tools.rag_tools import (
    add_documents,
    clear_knowledge_base,
    find_missing_rfcs,
    query_knowledge_base,
)


async def download_rfc_text(rfc_id: str) -> str:
    """Download RFC text from the official editor asynchronously."""
    normalized_rfc_id = normalize_rfc_id(rfc_id)
    url = cfg.RFC_BASE_URL.format(rfc_id=normalized_rfc_id)

    print(f"Downloading RFC {normalized_rfc_id} from {url}...", file=sys.stderr)
    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to download RFC {normalized_rfc_id}. Status code: {response.status_code}"
        )

    return response.text


def chunk_rfc_text(text: str, rfc_id: str) -> list[Document]:
    """Split RFC text into chunks for RAG indexing."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )

    documents = text_splitter.create_documents([text])
    normalized_rfc_id = normalize_rfc_id(rfc_id)
    for document in documents:
        document.metadata = {
            "source": f"RFC {normalized_rfc_id}",
            "rfc_id": normalized_rfc_id,
        }
    return documents


async def ingest_rfc_document(rfc_id: str) -> dict[str, Any]:
    """Download, chunk, and persist one RFC document."""
    normalized_rfc_id = normalize_rfc_id(rfc_id)
    text = await download_rfc_text(normalized_rfc_id)
    chunks = await asyncio.to_thread(chunk_rfc_text, text, normalized_rfc_id)
    await asyncio.to_thread(add_documents, chunks)
    return {"rfc_id": normalized_rfc_id, "chunks": len(chunks)}


async def preload_rfc_documents(rfc_ids: Sequence[str]) -> list[dict[str, Any]]:
    """Preload a fixed list of RFCs into the knowledge base."""
    results = []
    for rfc_id in rfc_ids:
        result = await ingest_rfc_document(rfc_id)
        results.append(result)
    return results


async def clear_rfc_knowledge_base() -> None:
    """Remove all RFC content from the knowledge base."""
    await asyncio.to_thread(clear_knowledge_base)


async def get_missing_rfc_ids(rfc_ids: Sequence[str]) -> list[str]:
    """Return RFC ids that are not currently indexed."""
    normalized_rfc_ids = [normalize_rfc_id(rfc_id) for rfc_id in rfc_ids]
    return await asyncio.to_thread(find_missing_rfcs, normalized_rfc_ids)


async def search_rfc_knowledge(query: str, rfc_ids: Sequence[str] | None = None) -> str:
    """Search the indexed RFC knowledge base for relevant sections."""
    normalized_rfc_ids = [normalize_rfc_id(rfc_id) for rfc_id in rfc_ids] if rfc_ids else None
    results = await asyncio.to_thread(
        query_knowledge_base,
        query,
        5,
        normalized_rfc_ids,
    )

    if not results:
        return "No relevant information found in the knowledge base."

    context_list = []
    for document in results:
        context_list.append(
            f"[Source: {document.metadata.get('source', 'Unknown')}]\n{document.page_content}"
        )

    return "\n\n---\n\n".join(context_list)
