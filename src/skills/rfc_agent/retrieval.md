---
name: rfc-expert-retrieval
description: Retrieval-stage guidance for ordering RFC tool calls and handling download or search failures conservatively.
---

# Retrieval Skill

## Workflow
1. If a concrete RFC is required, call `check_rfc_status(rfc_id)`.
2. If the RFC is missing, call `add_rfc(rfc_id)`.
3. If download succeeded or RFC text was not required, call `search_rfc_knowledge(query)`.

## Tool Constraints
- Never call `add_rfc` before checking local availability when an RFC number is known.
- Never call `add_rfc` when the plan does not require RFC content.
- Always use `search_rfc_knowledge` for the final retrieval step if a query exists.

## Error Handling
- If `add_rfc` fails, stop retrieval and let the answer stage explain the missing RFC context.
- If `search_rfc_knowledge` fails, surface the retrieval failure clearly.
- If search returns no relevant information, treat that as an empty result, not as a successful citation.
