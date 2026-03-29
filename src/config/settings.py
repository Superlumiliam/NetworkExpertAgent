import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenRouter Configuration
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Model Configuration
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL")

# RAG Configuration
RFC_BASE_URL = "https://www.rfc-editor.org/rfc/rfc{rfc_id}.txt"
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")
SUPABASE_VECTOR_TABLE = os.getenv("SUPABASE_VECTOR_TABLE", "rfc_knowledge_base")
SUPABASE_VECTOR_MATCH_FUNCTION = os.getenv(
    "SUPABASE_VECTOR_MATCH_FUNCTION", "match_rfc_documents"
)
SUPABASE_VECTOR_DIM = int(os.getenv("SUPABASE_VECTOR_DIM", "1536"))
SUPABASE_VECTOR_DISTANCE = os.getenv("SUPABASE_VECTOR_DISTANCE", "cosine").lower()

# Embedding Configuration
EMBEDDING_API_BASE_URL = os.getenv("EMBEDDING_API_BASE_URL")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")

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
