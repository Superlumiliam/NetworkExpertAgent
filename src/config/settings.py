import os
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenRouter Configuration
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Model Configuration
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openrouter/hunter-alpha")
MODEL_PROVIDER = "openai"

# RAG Configuration
CHROMA_PATH = os.getenv("CHROMA_PATH", os.path.join(os.getcwd(), "data", "chroma_db"))
RFC_BASE_URL = "https://www.rfc-editor.org/rfc/rfc{rfc_id}.txt"
VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "chroma").strip().lower() or "chroma"

# Embedding Configuration
# Use a lightweight, high-performance local embedding model
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# LangSmith Configuration
# Check if API key is present, if so, enable tracing unless explicitly disabled
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
ENABLE_LANGSMITH_TRACING = os.getenv("ENABLE_LANGSMITH_TRACING", "false").lower() == "true"

if LANGCHAIN_API_KEY and os.getenv("ENABLE_LANGSMITH_TRACING") is None:
    # If API key exists but ENABLE_LANGSMITH_TRACING is not set, default to True
    ENABLE_LANGSMITH_TRACING = True

# Ensure LANGCHAIN_TRACING_V2 is set if enabled
if ENABLE_LANGSMITH_TRACING:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "NetworkExpertAgent")

if VECTOR_BACKEND not in {"chroma", "pgvector"}:
    raise ValueError("VECTOR_BACKEND must be either 'chroma' or 'pgvector'.")


def get_database_url() -> str | None:
    """Return a psycopg-safe DATABASE_URL, encoding raw credentials when needed."""
    if not DATABASE_URL:
        return None

    if "://" not in DATABASE_URL:
        return DATABASE_URL

    parts = urlsplit(DATABASE_URL)
    if "@" not in parts.netloc:
        return DATABASE_URL

    userinfo, hostinfo = parts.netloc.rsplit("@", 1)
    if ":" not in userinfo:
        return DATABASE_URL

    username, password = userinfo.split(":", 1)
    encoded_userinfo = f"{quote(username, safe='')}:{quote(password, safe='')}"

    query_pairs = dict(parse_qsl(parts.query, keep_blank_values=True))
    if hostinfo.endswith(".supabase.co:5432") and "sslmode" not in query_pairs:
        query_pairs["sslmode"] = "require"

    normalized_query = urlencode(query_pairs)
    return urlunsplit(
        (
            parts.scheme,
            f"{encoded_userinfo}@{hostinfo}",
            parts.path,
            normalized_query,
            parts.fragment,
        )
    )
