# RFC Expert Skills

## Core Skills

### 1. Retrieve RFC Document
- **Description**: Download and index an RFC document from the IETF website.
- **When to use**: When the user asks about a specific RFC number (e.g., "What is RFC 7540?") or when the knowledge base does not contain the necessary information to answer a question about a specific protocol.
- **Tool**: `add_rfc(rfc_id)`

### 2. Search Knowledge Base
- **Description**: Search the local knowledge base for relevant sections of RFC documents.
- **When to use**: When the user asks specific technical questions about protocols, headers, fields, or behaviors defined in RFCs.
- **Tool**: `search_rfc_knowledge(query)`

## Decision Process

1. **Identify Protocol/RFC**: Extract the RFC number or protocol name from the user's question.
2. **Check Local Availability**: Check if the RFC is already in the knowledge base (conceptually). If not, download it.
3. **Search**: Query the knowledge base with specific terms related to the user's question.
4. **Synthesize**: Combine the search results to form a comprehensive answer.
