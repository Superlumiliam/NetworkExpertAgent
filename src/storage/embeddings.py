from __future__ import annotations

import sys
from typing import Optional

from langchain_huggingface import HuggingFaceEmbeddings

import src.config.settings as cfg


_embeddings: Optional[HuggingFaceEmbeddings] = None


def get_embeddings() -> HuggingFaceEmbeddings:
    """Load the shared embedding model lazily."""
    global _embeddings
    if _embeddings is None:
        print(f"Loading embedding model: {cfg.EMBEDDING_MODEL_NAME}...", file=sys.stderr)
        _embeddings = HuggingFaceEmbeddings(model_name=cfg.EMBEDDING_MODEL_NAME)
    return _embeddings
