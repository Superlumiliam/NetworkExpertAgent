import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenRouter Configuration
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Model Configuration
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openrouter/hunter-alpha")
MODEL_PROVIDER = "openai"

# RAG Configuration
CHROMA_PATH = os.path.join(os.getcwd(), "data", "chroma_db")
RFC_BASE_URL = "https://www.rfc-editor.org/rfc/rfc{rfc_id}.txt"

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
