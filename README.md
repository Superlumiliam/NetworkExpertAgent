# Network Expert Agent

An advanced AI Agent specializing in network protocols and RFCs, powered by RAG (Retrieval-Augmented Generation) and LangGraph.

## Features

- **Intelligent Routing**: Automatically directs queries to either the RFC Expert or a General Chat Agent for faster responses.
- **Stateful Execution**: Uses `LangGraph` to manage the agent's workflow (Analyze -> CheckLocal -> Download/Search -> Answer), reducing hallucinations.
- **Automated RFC Management**: Automatically downloads and indexes RFC documents from `rfc-editor.org` when needed.
- **Local RAG Knowledge Base**: Efficiently stores and retrieves protocol details using ChromaDB and local embeddings (HuggingFace).
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
    ```

2.  **Run the Agent:**
    ```bash
    uv run network-expert
    # Or directly with python:
    # python -m src.main
    ```

3.  **Interact with the Agent:**
    - Ask technical questions: "What is the default query interval in IGMPv3?"
    - Ask general questions: "Hello, how are you?" (routed to General Agent)
    - The agent will automatically download relevant RFCs if they are missing from the knowledge base.

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
│   └── test_agents.py      # Unit Tests
├── docs/                   # Documentation
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
