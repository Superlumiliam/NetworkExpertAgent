# RFC Expert Agent

An AI Agent that specializes in interpreting RFC network protocols using RAG (Retrieval-Augmented Generation) and MCP (Model Context Protocol).

## Features

- **Automated RFC Download**: Fetches RFC text directly from `rfc-editor.org`.
- **RAG Knowledge Base**: Chunks and stores RFC content in a local ChromaDB vector database.
- **MCP Integration**: Implements a custom MCP Server (`rfc_server.py`) that exposes tools to the agent.
- **Interactive Agent**: A CLI agent (`agent_client.py`) that queries the knowledge base to answer user questions.

## Prerequisites

- Python 3.10 or higher
- OpenAI API Key

## Installation

1.  **Clone/Download this repository.**
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Set your OpenAI API Key:**
    - Windows (PowerShell): `$env:OPENAI_API_KEY="your-key-here"`
    - Linux/Mac: `export OPENAI_API_KEY="your-key-here"`

2.  **Run the Agent:**
    ```bash
    python agent_client.py
    ```

3.  **Interact with the Agent:**
    - Ask questions like: "What is the frame structure in HTTP/2?"
    - If the agent doesn't know, tell it to download the RFC: "Download RFC 7540".
    - Then ask the question again.

## Architecture

- **`rag_utils.py`**: Core logic for downloading, chunking, embedding (OpenAI), and storing (ChromaDB) RFCs.
- **`rfc_server.py`**: An MCP Server that wraps `rag_utils.py` and exposes `add_rfc` and `search_rfc_knowledge` as tools.
- **`agent_client.py`**: An MCP Client that connects to the server via stdio, manages the chat loop, and uses OpenAI to generate answers based on tool outputs.

## Customization

- **Embeddings**: Modify `rag_utils.py` to use different embedding models (e.g., HuggingFace) if you want to avoid OpenAI for embeddings.
- **LLM**: The agent uses `gpt-4o` by default. You can change the model in `agent_client.py`.
