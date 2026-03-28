---
name: rfc-expert-planning
description: Planning-stage guidance for inferring RFC IDs, deciding whether RFC text is required, and producing an English retrieval query.
---

# Planning Skill

## Goals
- Convert the user request into a retrieval plan.
- Produce one English query that matches likely RFC wording.

## Planning Rules
- If the user gave an RFC number, preserve it.
- If the user named a well-known protocol but not an RFC, infer the canonical RFC only when you are confident.
- Set `needs_rfc_content=true` for standards questions that require exact behavior, timer values, field semantics, packet formats, or normative language.
- Set `should_check_local=true` only when there is an RFC number and RFC text is needed.

## Query Rules
- Queries must be in English.
- Prefer terms RFC text is likely to contain, such as field names, timer names, default values, and section vocabulary.
- Keep the query short and specific, for example `IGMPv3 Query Interval default value`.

## Failure Strategy
- If you cannot infer an RFC number confidently, leave `rfc_id` null and still generate a strong query.
- Favor retrieval over speculation.
