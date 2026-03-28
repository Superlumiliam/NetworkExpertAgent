---
name: rfc-expert-intent
description: Intent-stage guidance for classifying RFC and protocol questions before retrieval.
---

# Intent Skill

## Goals
- Detect whether the user is asking about a specific RFC, a protocol topic, or a detailed networking behavior.
- Distinguish direct RFC lookup from broader networking chat.

## Extraction Rules
- If the question contains an explicit RFC like `RFC 7540`, capture that as the strongest signal.
- If there is no RFC number, identify the protocol or feature the user cares about in concise English.
- Treat questions about defaults, timers, flags, packet fields, state machines, requirements, and interoperability as likely RFC-backed technical questions.

## Output Expectations
- Produce a short English topic summary.
- Capture confidence as a rough estimate of how likely the question needs RFC-backed retrieval.
- Avoid solving the problem in this stage; only classify it cleanly.
