"""Retrieval pipeline configuration."""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path


class RetrievalMode(str, Enum):
    BASIC = "basic"
    ADVANCED = "advanced"


def get_retrieval_mode() -> RetrievalMode:
    raw = os.getenv("RAG_RETRIEVAL_MODE", "advanced").lower()
    if raw not in ("basic", "advanced"):
        raise ValueError(f"RAG_RETRIEVAL_MODE must be 'basic' or 'advanced', got: {raw!r}")
    return RetrievalMode(raw)


def bm25_index_path() -> Path:
    chroma = Path(os.getenv("CHROMA_PATH", "./chroma_db"))
    return chroma / "bm25_index.json"


def candidate_multiplier() -> int:
    return int(os.getenv("RAG_CANDIDATE_MULTIPLIER", "4"))


def rerank_model_name() -> str:
    return os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
