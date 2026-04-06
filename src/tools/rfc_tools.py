import asyncio
import re
import sys
from dataclasses import dataclass
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

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

_NUMBERED_HEADING_RE = re.compile(r"^(?P<section_id>\d+(?:\.\d+)*)\.\s+(?P<title>.+)$")
_APPENDIX_HEADING_RE = re.compile(r"^Appendix\s+(?P<section_id>[A-Z])\.\s+(?P<title>.+)$")
_APPENDIX_SUBSECTION_RE = re.compile(r"^(?P<section_id>[A-Z](?:\.\d+)+)\.?\s+(?P<title>.+)$")
_RFC_HEADER_RE = re.compile(
    r"^RFC\s+\d+\b.*\b("
    r"January|February|March|April|May|June|July|August|September|October|November|December"
    r")\s+\d{4}$"
)
_TOC_LINE_RE = re.compile(r"(?:\. ?){3,}\s*\d+\s*$")
_BACK_MATTER_HEADINGS = {
    "authors' addresses",
    "author's address",
    "full copyright statement",
    "copyright notice",
    "intellectual property",
}


@dataclass(frozen=True)
class RFCSectionHeading:
    section_id: str
    title: str
    kind: str
    level: int


@dataclass(frozen=True)
class RFCSection:
    section_id: str
    title: str
    kind: str
    level: int
    body: str


def _create_text_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )


def _clean_heading_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().rstrip(". ")


def _looks_like_heading_title(title: str) -> bool:
    cleaned = _clean_heading_title(title)
    if not cleaned:
        return False
    if len(cleaned) > 120:
        return False
    if len(cleaned.split()) > 15:
        return False
    if _TOC_LINE_RE.search(cleaned):
        return False
    if cleaned.endswith(":"):
        return False
    return True


def _parse_section_heading(line: str) -> RFCSectionHeading | None:
    stripped = line.strip()
    if not stripped:
        return None

    appendix_match = _APPENDIX_HEADING_RE.match(stripped)
    if appendix_match:
        title = appendix_match.group("title")
        if _looks_like_heading_title(title):
            return RFCSectionHeading(
                section_id=appendix_match.group("section_id"),
                title=_clean_heading_title(title),
                kind="appendix",
                level=1,
            )

    appendix_subsection_match = _APPENDIX_SUBSECTION_RE.match(stripped)
    if appendix_subsection_match:
        title = appendix_subsection_match.group("title")
        if _looks_like_heading_title(title):
            section_id = appendix_subsection_match.group("section_id")
            return RFCSectionHeading(
                section_id=section_id,
                title=_clean_heading_title(title),
                kind="appendix",
                level=section_id.count(".") + 1,
            )

    numbered_match = _NUMBERED_HEADING_RE.match(stripped)
    if numbered_match:
        title = numbered_match.group("title")
        if _looks_like_heading_title(title):
            section_id = numbered_match.group("section_id")
            return RFCSectionHeading(
                section_id=section_id,
                title=_clean_heading_title(title),
                kind="section",
                level=section_id.count(".") + 1,
            )

    return None


def _is_page_artifact(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if "[Page " in stripped:
        return True
    if _RFC_HEADER_RE.match(stripped):
        return True
    return False


def _normalize_rfc_lines(text: str) -> list[str]:
    normalized_lines: list[str] = []
    in_table_of_contents = False

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n").split("\n"):
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            if not in_table_of_contents and normalized_lines and normalized_lines[-1] != "":
                normalized_lines.append("")
            continue

        if stripped == "Table of Contents":
            in_table_of_contents = True
            continue

        if _is_page_artifact(stripped):
            continue

        if in_table_of_contents:
            if _parse_section_heading(stripped):
                in_table_of_contents = False
            else:
                continue

        normalized_lines.append(stripped)

    while normalized_lines and normalized_lines[-1] == "":
        normalized_lines.pop()

    return normalized_lines


def _collapse_section_lines(lines: list[str]) -> str:
    paragraphs: list[str] = []
    current_paragraph: list[str] = []

    def flush_paragraph() -> None:
        if current_paragraph:
            paragraphs.append(" ".join(current_paragraph))
            current_paragraph.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue

        if current_paragraph and current_paragraph[-1].endswith("-"):
            current_paragraph[-1] = current_paragraph[-1][:-1] + stripped
            continue

        current_paragraph.append(stripped)

    flush_paragraph()
    return "\n\n".join(paragraphs).strip()


def _is_back_matter_heading(line: str) -> bool:
    normalized = _clean_heading_title(line).lower()
    return normalized in _BACK_MATTER_HEADINGS


def _make_special_section(kind: str, lines: list[str]) -> RFCSection | None:
    body = _collapse_section_lines(lines)
    if not body:
        return None

    title = "Front Matter" if kind == "front_matter" else "Back Matter"
    return RFCSection(
        section_id=kind,
        title=title,
        kind=kind,
        level=0,
        body=body,
    )


def _parse_rfc_sections(text: str) -> list[RFCSection]:
    lines = _normalize_rfc_lines(text)
    if not lines:
        return []

    sections: list[RFCSection] = []
    current_heading: RFCSectionHeading | None = None
    current_lines: list[str] = []
    pending_lines: list[str] = []
    back_matter_lines: list[str] = []
    in_back_matter = False
    seen_numbered_section = False

    def flush_current_section() -> None:
        nonlocal current_heading, current_lines
        if current_heading is None:
            return
        body = _collapse_section_lines(current_lines)
        sections.append(
            RFCSection(
                section_id=current_heading.section_id,
                title=current_heading.title,
                kind=current_heading.kind,
                level=current_heading.level,
                body=body,
            )
        )
        current_heading = None
        current_lines = []

    for line in lines:
        stripped = line.strip()

        if in_back_matter:
            back_matter_lines.append(stripped)
            continue

        heading = _parse_section_heading(stripped)
        if heading:
            if current_heading is None and pending_lines:
                front_matter = _make_special_section("front_matter", pending_lines)
                if front_matter is not None:
                    sections.append(front_matter)
                pending_lines = []
            else:
                flush_current_section()

            current_heading = heading
            current_lines = []
            seen_numbered_section = True
            continue

        if seen_numbered_section and current_heading is not None and _is_back_matter_heading(stripped):
            flush_current_section()
            in_back_matter = True
            back_matter_lines = [stripped]
            continue

        if current_heading is None:
            pending_lines.append(stripped)
        else:
            current_lines.append(stripped)

    if current_heading is None and pending_lines:
        front_matter = _make_special_section("front_matter", pending_lines)
        if front_matter is not None:
            sections.append(front_matter)
    else:
        flush_current_section()

    if back_matter_lines:
        back_matter = _make_special_section("back_matter", back_matter_lines)
        if back_matter is not None:
            sections.append(back_matter)

    return sections


def _build_chunk_label(rfc_id: str, section: RFCSection) -> str:
    normalized_rfc_id = normalize_rfc_id(rfc_id)
    if section.kind == "section":
        return f"RFC {normalized_rfc_id} / Section {section.section_id} / {section.title}"
    if section.kind == "appendix":
        return f"RFC {normalized_rfc_id} / Appendix {section.section_id} / {section.title}"
    return f"RFC {normalized_rfc_id} / {section.title}"


def _build_section_metadata(rfc_id: str, section: RFCSection) -> dict[str, Any]:
    source = _build_chunk_label(rfc_id, section)
    return {
        "source": source,
        "rfc_id": normalize_rfc_id(rfc_id),
        "section_id": section.section_id,
        "section_title": section.title,
        "section_kind": section.kind,
        "section_level": section.level,
    }


def _split_section_body(section: RFCSection) -> list[str]:
    if not section.body:
        return [""]
    return _create_text_splitter().split_text(section.body)


def _build_section_documents(section: RFCSection, rfc_id: str) -> list[Document]:
    label = _build_chunk_label(rfc_id, section)
    base_metadata = _build_section_metadata(rfc_id, section)
    body_chunks = _split_section_body(section)
    total_chunks = len(body_chunks)
    documents: list[Document] = []

    for index, body_chunk in enumerate(body_chunks, start=1):
        metadata = {
            **base_metadata,
            "section_chunk_index": index,
            "section_chunk_count": total_chunks,
        }
        page_content = label if not body_chunk else f"{label}\n\n{body_chunk}"
        documents.append(Document(page_content=page_content, metadata=metadata))

    return documents


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
    """Split RFC text into section-aware chunks for RAG indexing."""
    sections = _parse_rfc_sections(text)
    if not sections:
        fallback_section = RFCSection(
            section_id="front_matter",
            title="Front Matter",
            kind="front_matter",
            level=0,
            body=_collapse_section_lines(text.splitlines()),
        )
        sections = [fallback_section]

    documents: list[Document] = []
    for section in sections:
        documents.extend(_build_section_documents(section, rfc_id))
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
