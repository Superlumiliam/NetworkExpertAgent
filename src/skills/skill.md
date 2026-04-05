# RFC Expert Skills

## Core Skills

### 1. Search Knowledge Base
- **Description**: Search the local knowledge base for relevant sections of RFC documents.
- **When to use**: When the user asks specific technical questions about the preloaded IGMP, MLD, or PIM protocols.
- **Tool**: `search_rfc_knowledge(query, rfc_ids)`

## Decision Process

1. **Identify Protocol/RFC**: Extract the RFC number or protocol name from the user's question.
2. **Check Preloaded Scope**: Only continue if the request maps to preloaded IGMPv3, MLDv2, or PIM-SM RFCs.
3. **Search**: Query the knowledge base within the allowed RFC scope.
4. **Respond**: Answer from retrieved context, or directly say the protocol/RFC is not preloaded.
