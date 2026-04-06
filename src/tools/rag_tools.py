import hashlib
import re
import sys
from typing import Any, List, Optional
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

import src.config.settings as cfg

_embeddings: Optional[OpenAIEmbeddings] = None


def _validate_identifier(value: str, env_var_name: str) -> str:
    """Allow only simple SQL identifiers because table/function names come from env vars."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise RuntimeError(
            f"Invalid {env_var_name} value '{value}'. Use an unqualified SQL identifier."
        )
    return value


def _get_db_connection():
    """Open a psycopg connection with pgvector adapters registered."""
    missing = []
    if not cfg.SUPABASE_DB_URL:
        missing.append("SUPABASE_DB_URL")
    if not cfg.SUPABASE_VECTOR_TABLE:
        missing.append("SUPABASE_VECTOR_TABLE")
    if missing:
        missing_vars = ", ".join(missing)
        raise RuntimeError(
            "Supabase vector store is not configured. Missing "
            f"{missing_vars}. Add them to your .env file before using RFC indexing/search."
        )

    if cfg.SUPABASE_VECTOR_DISTANCE != "cosine":
        raise RuntimeError(
            "Unsupported SUPABASE_VECTOR_DISTANCE value. Only 'cosine' is supported."
        )

    try:
        import psycopg
        from pgvector.psycopg import register_vector
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "Supabase vector dependencies are not installed. Run `uv sync`."
        ) from exc

    normalized_db_url = _normalize_postgres_url(cfg.SUPABASE_DB_URL)
    _validate_supabase_connection_string(normalized_db_url)

    try:
        conn = psycopg.connect(
            normalized_db_url,
            row_factory=dict_row,
            prepare_threshold=None,
        )
    except Exception as exc:
        raise RuntimeError(_format_connection_error(normalized_db_url, exc)) from exc

    try:
        _prepare_connection_for_pgvector(conn, register_vector)
    except Exception as exc:
        raise RuntimeError(_format_connection_error(normalized_db_url, exc)) from exc
    return conn


def _normalize_postgres_url(connection_string: str) -> str:
    """Percent-encode raw credentials in postgres URLs so special chars don't break parsing."""
    if "://" not in connection_string:
        return connection_string

    parts = urlsplit(connection_string)
    if "@" not in parts.netloc:
        return connection_string

    userinfo, hostinfo = parts.netloc.rsplit("@", 1)
    if ":" not in userinfo:
        safe_userinfo = quote(unquote(userinfo), safe="")
    else:
        username, password = userinfo.split(":", 1)
        safe_userinfo = (
            f"{quote(unquote(username), safe='')}:"
            f"{quote(unquote(password), safe='')}"
        )

    return urlunsplit(
        (
            parts.scheme,
            f"{safe_userinfo}@{hostinfo}",
            parts.path,
            parts.query,
            parts.fragment,
        )
    )


def _validate_supabase_connection_string(connection_string: str) -> None:
    """Catch the common Supabase host/port mismatch before psycopg raises a low-level error."""
    if "://" not in connection_string:
        return

    parts = urlsplit(connection_string)
    hostname = parts.hostname or ""
    port = parts.port

    if hostname.startswith("db.") and hostname.endswith(".supabase.co") and port == 6543:
        raise RuntimeError(
            "Your SUPABASE_DB_URL appears to use a direct database host with the pooler port 6543. "
            "Open Supabase Dashboard -> Connect and copy the exact pooler connection string instead. "
            "For shared pooler URLs, Supabase currently uses hosts like "
            "'aws-0-<region>.pooler.supabase.com' rather than 'db.<project-ref>.supabase.co'."
        )


def _format_connection_error(connection_string: str, exc: Exception) -> str:
    message = str(exc)
    if "failed to resolve host" in message:
        return (
            "Failed to resolve the Supabase database host. "
            "Please open Supabase Dashboard -> Connect and replace SUPABASE_DB_URL with the exact "
            "pooler connection string shown there. If you are using a shared pooler, the host should "
            "usually look like 'aws-0-<region>.pooler.supabase.com'."
        )
    if "vector type not found in the database" in message:
        return (
            "The pgvector extension could not be found for this database session. "
            "Make sure you have run `create extension if not exists vector with schema extensions;` "
            "in Supabase SQL Editor, and keep using the provided setup SQL before indexing RFCs."
        )
    return f"Failed to connect to Supabase: {message}"


def _prepare_connection_for_pgvector(conn, register_vector) -> None:
    with conn.cursor() as cur:
        cur.execute("SET search_path TO public, extensions")
    register_vector(conn)


def _assert_vector_dimension(vector: List[float]) -> None:
    if len(vector) != cfg.SUPABASE_VECTOR_DIM:
        raise RuntimeError(
            "Embedding dimension mismatch. "
            f"Expected {cfg.SUPABASE_VECTOR_DIM}, got {len(vector)}."
        )


def _normalize_metadata(metadata: Any) -> dict[str, Any]:
    if not metadata:
        return {}
    if isinstance(metadata, dict):
        return metadata
    raise RuntimeError("Document metadata must be a dictionary.")


def _json_value(value: dict[str, Any]):
    from psycopg.types.json import Json

    return Json(value)


def _vector_value(value: List[float]):
    from pgvector import Vector

    return Vector(value)

def get_embeddings() -> OpenAIEmbeddings:
    """Initialize remote embeddings using an OpenAI-compatible API."""
    global _embeddings
    if _embeddings is None:
        missing = []
        if not cfg.EMBEDDING_API_KEY:
            missing.append("EMBEDDING_API_KEY")
        if not cfg.EMBEDDING_MODEL_NAME:
            missing.append("EMBEDDING_MODEL_NAME")
        if missing:
            missing_vars = ", ".join(missing)
            raise RuntimeError(
                "Remote embeddings are not configured. Missing "
                f"{missing_vars}. Add them to your .env file before using RFC indexing/search."
            )

        print(
            "Loading remote embedding model "
            f"'{cfg.EMBEDDING_MODEL_NAME}' from {cfg.EMBEDDING_API_BASE_URL}...",
            file=sys.stderr,
        )
        _embeddings = OpenAIEmbeddings(
            model=cfg.EMBEDDING_MODEL_NAME,
            api_key=cfg.EMBEDDING_API_KEY,
            base_url=cfg.EMBEDDING_API_BASE_URL,
        )
    return _embeddings

def add_documents(documents: List[Document]) -> None:
    """Embed and store documents in Supabase Postgres."""
    if not documents:
        return

    table_name = _validate_identifier(cfg.SUPABASE_VECTOR_TABLE, "SUPABASE_VECTOR_TABLE")
    texts = [doc.page_content for doc in documents]
    metadata_items = [_normalize_metadata(doc.metadata) for doc in documents]
    embeddings = get_embeddings().embed_documents(texts)

    if len(embeddings) != len(documents):
        raise RuntimeError("Embedding provider returned an unexpected number of vectors.")

    rfc_ids = sorted(
        {
            str(metadata["rfc_id"]).strip()
            for metadata in metadata_items
            if metadata.get("rfc_id")
        }
    )

    for embedding in embeddings:
        _assert_vector_dimension(embedding)

    records = []
    for text, metadata, embedding in zip(texts, metadata_items, embeddings):
        records.append(
            (
                text,
                _json_value(metadata),
                _vector_value(embedding),
                hashlib.md5(text.encode("utf-8")).hexdigest(),
            )
        )

    with _get_db_connection() as conn:
        with conn.cursor() as cur:
            if rfc_ids:
                cur.execute(
                    f"DELETE FROM public.{table_name} WHERE rfc_id = ANY(%s)",
                    (rfc_ids,),
                )
            cur.executemany(
                f"""
                INSERT INTO public.{table_name} (content, metadata, embedding, content_hash)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (rfc_id, content_hash) DO NOTHING
                """,
                records,
            )

def clear_knowledge_base() -> None:
    """Remove all indexed RFC content from Supabase."""
    table_name = _validate_identifier(cfg.SUPABASE_VECTOR_TABLE, "SUPABASE_VECTOR_TABLE")

    with _get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE public.{table_name}")


def find_missing_rfcs(rfc_ids: List[str]) -> List[str]:
    """Return the RFC ids that are not present in Supabase."""
    if not rfc_ids:
        return []

    normalized_rfc_ids = sorted({str(rfc_id).strip() for rfc_id in rfc_ids})
    table_name = _validate_identifier(cfg.SUPABASE_VECTOR_TABLE, "SUPABASE_VECTOR_TABLE")

    with _get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT DISTINCT rfc_id
                FROM public.{table_name}
                WHERE rfc_id = ANY(%s)
                """,
                (normalized_rfc_ids,),
            )
            existing = {
                row["rfc_id"]
                for row in cur.fetchall()
                if row.get("rfc_id")
            }

    return [rfc_id for rfc_id in normalized_rfc_ids if rfc_id not in existing]


def query_knowledge_base(
    query: str,
    n_results: int = 5,
    rfc_ids: Optional[List[str]] = None,
) -> List[Document]:
    """Query the Supabase vector database for relevant documents."""
    table_name = _validate_identifier(cfg.SUPABASE_VECTOR_TABLE, "SUPABASE_VECTOR_TABLE")
    query_embedding = get_embeddings().embed_query(query)
    _assert_vector_dimension(query_embedding)
    filter_rfc_ids = sorted({str(rfc_id).strip() for rfc_id in rfc_ids}) if rfc_ids else None
    limited_results = max(1, min(int(n_results), 50))

    with _get_db_connection() as conn:
        with conn.cursor() as cur:
            query_sql = f"""
                SELECT
                    id,
                    content,
                    metadata,
                    1 - (embedding <=> %s::extensions.vector) AS similarity
                FROM public.{table_name}
            """
            params: list[Any] = [_vector_value(query_embedding)]

            if filter_rfc_ids:
                query_sql += " WHERE rfc_id = ANY(%s::text[])"
                params.append(filter_rfc_ids)

            query_sql += """
                ORDER BY embedding <=> %s::extensions.vector
                LIMIT %s::integer
            """
            params.extend([_vector_value(query_embedding), limited_results])

            cur.execute(query_sql, params)
            rows = cur.fetchall()

    return [
        Document(
            page_content=row["content"],
            metadata=_normalize_metadata(row.get("metadata")),
        )
        for row in rows
    ]

def check_rfc_exists(rfc_id: str) -> bool:
    """Check if an RFC is already indexed in Supabase."""
    table_name = _validate_identifier(cfg.SUPABASE_VECTOR_TABLE, "SUPABASE_VECTOR_TABLE")

    with _get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM public.{table_name} WHERE rfc_id = %s LIMIT 1",
                (rfc_id,),
            )
            return cur.fetchone() is not None
