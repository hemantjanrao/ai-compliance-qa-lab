"""Embedding config fails fast. Does not download MiniLM."""
from __future__ import annotations

import pytest

from scratch.embeddings import get_embedding_model_name, get_embedding_provider


def test_default_provider_is_local(monkeypatch):
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    assert get_embedding_provider() == "local"


def test_rejects_unknown_embedding_provider(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    with pytest.raises(ValueError, match="Session 2"):
        get_embedding_provider()


def test_model_name_default(monkeypatch):
    monkeypatch.delenv("LOCAL_EMBEDDING_MODEL", raising=False)
    assert get_embedding_model_name() == "all-MiniLM-L6-v2"
