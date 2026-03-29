# Network Expert Agent

An advanced AI Agent specializing in network protocols and RFCs, powered by RAG (Retrieval-Augmented Generation) and LangGraph.

## Features

- **Intelligent Routing**: Automatically directs queries to either the RFC Expert or a General Chat Agent for faster responses.
- **Stateful Execution**: Uses `LangGraph` to manage the agent's workflow (Analyze -> CheckLocal -> Download/Search -> Answer), reducing hallucinations.
- **Automated RFC Management**: Automatically downloads and indexes RFC documents from `rfc-editor.org` when needed.
- **Lightweight RAG Knowledge Base**: Efficiently stores and retrieves protocol details using Supabase pgvector and a remote embedding API.
- **Skill-Based Decision Making**: Dynamically loads skills to enhance agent capabilities.
- **Comprehensive Testing**: Includes unit tests and a benchmark suite for performance evaluation.

## Prerequisites

- Python 3.12 or higher
- OpenRouter API Key (for LLM access)

## Installation

1.  **Clone the repository.**
2.  **Install dependencies using `uv`:**
    ```bash
    # Install uv if not present
    pip install uv
    
    # Sync dependencies
    uv sync
    ```

## Usage

1.  **Set Environment Variables:**
    Create a `.env` file in the root directory:
    ```env
    OPENROUTER_API_KEY=your_openrouter_api_key_here
    DEFAULT_MODEL=deepseek/deepseek-chat  # Or your preferred model
    ENABLE_LANGSMITH_TRACING=false        # Set to true for debugging

    # Remote embedding API (OpenAI-compatible)
    EMBEDDING_API_BASE_URL=https://api.openai.com/v1
    EMBEDDING_API_KEY=sk-your-embedding-key
    EMBEDDING_MODEL_NAME=text-embedding-3-small

    # Supabase pgvector
    SUPABASE_DB_URL=postgresql://postgres.<project-ref>:<YOUR_DB_PASSWORD>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
    SUPABASE_VECTOR_TABLE=rfc_knowledge_base
    SUPABASE_VECTOR_MATCH_FUNCTION=match_rfc_documents
    SUPABASE_VECTOR_DIM=1536
    SUPABASE_VECTOR_DISTANCE=cosine
    ```
    `EMBEDDING_API_BASE_URL` should point to your embedding provider's OpenAI-compatible API root.
    `EMBEDDING_API_KEY` is the key issued by that provider.
    `EMBEDDING_MODEL_NAME` should be the provider's embedding model identifier.
    If you use a different compatible gateway, replace those three values with the ones from your service.
    `SUPABASE_DB_URL` should be copied exactly from Supabase `Connect`, preferably the pooler connection string shown there.
    Run the SQL in `db/init/supabase.sql` before starting the agent.

2.  **Run the Agent:**
    ```bash
    uv run network-expert
    # Or directly with python:
    # python -m src.main
    ```

    Run the Web UI:
    ```bash
    uv run network-expert-web
    # Open http://127.0.0.1:8000 in your browser
    ```

3.  **Interact with the Agent:**
    - Ask technical questions: "What is the default query interval in IGMPv3?"
    - Ask general questions: "Hello, how are you?" (routed to General Agent)
    - The agent will automatically download relevant RFCs if they are missing from the knowledge base.
    - Indexed RFC chunks are stored remotely in Supabase instead of the local filesystem.
    - Or use the browser UI for a chat-style workflow with the same backend capabilities.

## Project Structure

```text
NetworkExpertAgent/
├── src/                    # Source Code
│   ├── main.py             # Entry Point
│   ├── core/               # Core Components (Router, State)
│   ├── agents/             # Agent Implementations (RFC, General)
│   ├── tools/              # Tools (RFC Management, RAG)
│   ├── skills/             # Skill Definitions
│   └── config/             # Configuration
├── tests/                  # Tests
│   ├── benchmark.py        # Performance Benchmark
│   ├── quiz.md             # Benchmark Questions
│   ├── test_agents.py      # Unit Tests
│   └── test_rag_tools.py   # RAG Unit Tests
├── db/                     # Database bootstrap scripts
│   └── init/
│       └── supabase.sql
└── pyproject.toml          # Project Configuration
```

## Testing

Run the unit tests:
```bash
uv run python -m unittest tests/test_agents.py
```

Run the benchmark (requires API key):
```bash
uv run tests/benchmark.py
```

The benchmark score now combines:
- Answer accuracy: 70%
- Runtime: 30%

Baseline runtime grading per question:
- 0-30s: excellent
- 30-60s: good
- 60-120s: pass
- 120s: fail
