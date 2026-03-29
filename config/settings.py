# Configuration agent_client.py
SERVER_SCRIPT = "rfc_server.py"
# OpenRouter Configuration
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Default to a model that is available on OpenRouter
DEFAULT_MODEL = "deepseek/deepseek-v3.2"
MODEL_PROVIDER = "openai"

# Configuration rag_utils.py
CHROMA_PATH = "./data/chroma_db"
RFC_BASE_URL = "https://www.rfc-editor.org/rfc/rfc{rfc_id}.txt"

# embedding model
EMBEDDING_API_BASE_URL = "https://api.openai.com/v1"
EMBEDDING_MODEL_NAME = "text-embedding-3-small"
