---
name: rfc-expert-agent
description: Use this skill when answering RFC, IETF protocol, packet field, timer default, or standards-behavior questions that benefit from RFC-backed retrieval.
---

# RFC Expert Agent Skill

## When to use this skill
- Use this skill for questions about RFC numbers, protocol behavior, packet formats, timer defaults, option semantics, interoperability rules, and IETF standards details.
- Do not use this skill for casual chat or non-networking questions.

## How this skill works
This skill uses progressive disclosure:

1. Discovery: load this file to identify when RFC-backed reasoning is needed.
2. Activation: load the phase-specific references needed for the current step.
3. Execution: follow the runtime workflow and call tools only when the retrieval phase requires them.

## Runtime workflow
1. Intent: classify the user request and identify the real networking target.
2. Planning: infer an RFC number when confidence is high, and produce one English retrieval query.
3. Retrieval: check local RFC availability, optionally download the RFC, then search the knowledge base.
4. Answering: answer with clear provenance, separating RFC-backed facts from general knowledge.

## Tool contract
- `check_rfc_status(rfc_id)`: confirm whether a concrete RFC already exists in the local knowledge base.
- `add_rfc(rfc_id)`: download and index a concrete RFC only when RFC text is required and missing locally.
- `search_rfc_knowledge(query)`: retrieve relevant RFC passages using the final English query.

## Reference files
- `base.md`: shared operating rules and tool policy.
- `intent.md`: how to classify the question.
- `planning.md`: how to derive RFC IDs and search queries.
- `retrieval.md`: tool ordering and failure handling.
- `answering.md`: answer formatting and evidence rules.
