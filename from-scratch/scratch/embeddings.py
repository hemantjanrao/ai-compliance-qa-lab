"""Embedding config — Session 2 uses local MiniLM (no API key).

An embedding turns text into a vector (a list of numbers). Similar
meaning → similar direction. Never mix two embedding models in one
Chroma collection; delete and re-ingest if you change the model.

This module does not load the model at import time. Unit tests only
check the config. `make ingest` loads MiniLM when it first embeds.
"""
from __future__ import annotations

import os
from typing import Literal

EmbeddingProvider = Literal["local"]
LOCAL_MODEL = "all-MiniLM-L6-v2"


def get_embedding_provider() -> EmbeddingProvider:
    provider = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower() or "local"
    if provider != "local":
        raise ValueError(
            f"EMBEDDING_PROVIDER={provider!r} is not supported in Session 2. "
            "Use 'local' (free MiniLM, no API key)."
        )
    return "local"


def get_embedding_model_name() -> str:
    get_embedding_provider()
    return os.getenv("LOCAL_EMBEDDING_MODEL", LOCAL_MODEL)
