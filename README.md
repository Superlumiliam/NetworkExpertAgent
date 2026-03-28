# Network Expert Agent

An advanced AI agent specializing in network protocols and RFCs, powered by local RAG (Retrieval-Augmented Generation), progressive skill loading, and RFC-aware tool orchestration.

Current version: `v0.3.0`

## Features

- **Intelligent Routing**: Automatically directs queries to either the RFC Expert or a General Chat Agent for faster responses.
- **Skill Runtime for RFC Queries**: The RFC expert now runs through a four-stage skill-driven pipeline: `Intent -> Planning -> Retrieval -> Answering`.
- **Progressive Skill Disclosure**: Loads `SKILL.md` and stage-specific skill files only when needed, reducing prompt noise and simplifying maintenance.
- **Automated RFC Management**: Automatically downloads and indexes RFC documents from `rfc-editor.org` when needed.
- **Local RAG Knowledge Base**: Efficiently stores and retrieves protocol details using ChromaDB and local embeddings (HuggingFace).
- **Vercel-Ready Web App**: FastAPI-powered same-origin web UI and API routes that keep model credentials on the server side.
- **Pluggable Vector Storage**: Uses local Chroma in development and `pgvector`-backed Postgres in production.
- **Robust Structured Output Handling**: Tolerates non-standard model outputs, including tool-call-like responses from free or weaker models.
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
    VECTOR_BACKEND=chroma                 # Use pgvector on Vercel/production
    DATABASE_URL=postgresql://...         # Required when VECTOR_BACKEND=pgvector
    CHROMA_PATH=/tmp/network-expert-db    # Optional override for ephemeral environments
    ```

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
    - The RFC expert uses progressive skills from `src/skills/rfc_agent/` and keeps the public `rfc_agent.ainvoke(...)` interface stable.
    - Or use the browser UI for a chat-style workflow with the same backend capabilities.

## Project Structure

```text
NetworkExpertAgent/
├── src/                    # Source Code
│   ├── main.py             # Entry Point
│   ├── core/               # Core Components (Router, State)
│   ├── agents/             # Agent Implementations (RFC Skill Runtime, General)
│   ├── tools/              # Tools (RFC Management, RAG)
│   ├── skills/             # Skill Definitions
│   └── config/             # Configuration
├── tests/                  # Tests
│   ├── benchmark.py        # Performance Benchmark
│   ├── quiz.md             # Benchmark Questions
│   └── test_agents.py      # Unit Tests
├── docs/                   # Documentation
└── pyproject.toml          # Project Configuration
```

## Testing

Run the unit tests:
```bash
uv run python -m unittest tests/test_agents.py tests/test_storage.py tests/test_web_app.py
```

Run the benchmark (requires API key and model access):
```bash
uv run python tests/benchmark.py
```

## Vercel Deployment

This project is deployed to Vercel as a single Python web app. The browser only talks to the same-origin app routes, while `OPENROUTER_API_KEY` stays in server-side environment variables.

Recommended production environment variables:

```env
OPENROUTER_API_KEY=...
DEFAULT_MODEL=...
ENABLE_LANGSMITH_TRACING=false
LANGCHAIN_API_KEY=...           # Optional, only if tracing is enabled
VECTOR_BACKEND=pgvector
DATABASE_URL=postgresql://...
```

To seed the managed `pgvector` database from the local Chroma index before the first preview deployment:

```bash
uv run python scripts/seed_pgvector_from_chroma.py
```

The Vercel runtime is configured through [`vercel.json`](vercel.json) with:
- same-origin rewrites to the FastAPI app entrypoint
- Python function memory `3009`
- Python function max duration `60`
- function bundle exclusions for `tests/`, `docs/`, `.venv/`, and `data/`

The benchmark score now combines:
- Answer accuracy: 70%
- Runtime: 30%

Baseline runtime grading per question:
- 0-30s: excellent
- 30-60s: good
- 60-120s: pass
- 120s: fail

## RFC Skill Layout

The RFC expert skill set is organized under `src/skills/rfc_agent/`:

- `SKILL.md`: skill metadata and top-level runtime contract
- `base.md`: shared rules and tool policy
- `intent.md`: question classification guidance
- `planning.md`: RFC/query planning guidance
- `retrieval.md`: tool-order and failure-handling guidance
- `answering.md`: answer synthesis rules

For the v0.3.0 refactor notes, see `docs/refactoring_v0.3.0_rfc_agent_skills.md`.
