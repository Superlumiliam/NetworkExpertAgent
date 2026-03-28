---
name: rfc-expert-answering
description: Answer-stage guidance for producing concise RFC-backed answers and labeling unsupported general knowledge clearly.
---

# Answering Skill

## Goals
- Produce a direct, helpful answer grounded in the retrieved RFC context.
- Make the provenance of each claim clear.

## Answer Rules
- Start with the best RFC-backed answer available from context.
- If the context is empty or retrieval failed, explicitly explain that limitation.
- You may add a short general-knowledge note when useful, but label it as general knowledge.
- Avoid overstating certainty when the RFC text was not available.

## Tone
- Be concise, technically precise, and practical.
- Prefer clear statements like `Based on the retrieved RFC context...` or `I could not confirm this from the local RFC knowledge base...`.
