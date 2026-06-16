"""Embedding provider abstraction — local (free) or OpenAI."""
from __future__ import annotations

import os
from typing import Literal

import numpy as np
from chromadb import EmbeddingFunction, Documents, Embeddings
from chromadb.utils.embedding_functions import (
    OpenAIEmbeddingFunction,
    SentenceTransformerEmbeddingFunction,
)

EmbeddingProvider = Literal["local", "openai"]

_LOCAL_MODEL = "all-MiniLM-L6-v2"
_OPENAI_MODEL = "text-embedding-3-small"


def get_embedding_provider() -> EmbeddingProvider:
    provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    if provider not in ("local", "openai"):
        raise ValueError(f"EMBEDDING_PROVIDER must be 'local' or 'openai', got: {provider!r}")
    return provider  # type: ignore[return-value]


def get_chroma_embedding_function() -> EmbeddingFunction[Documents]:
    if get_embedding_provider() == "openai":
        return OpenAIEmbeddingFunction(
            api_key=os.environ["OPENAI_API_KEY"],
            model_name=os.getenv("EMBEDDING_MODEL", _OPENAI_MODEL),
        )
    return SentenceTransformerEmbeddingFunction(
        model_name=os.getenv("LOCAL_EMBEDDING_MODEL", _LOCAL_MODEL),
        device=os.getenv("EMBEDDING_DEVICE", "cpu"),
        normalize_embeddings=True,
    )


def embed_text(text: str) -> np.ndarray:
    """Single-text embed for eval helpers (metamorphic / bias tests)."""
    fn = get_chroma_embedding_function()
    vectors: Embeddings = fn([text])
    return np.array(vectors[0])
