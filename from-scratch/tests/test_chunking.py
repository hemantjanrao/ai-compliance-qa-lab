"""Chunking and metadata — fast, no vector DB."""
from __future__ import annotations

import pytest

from scratch.chunking import MAX_ARTICLE, chunk_metadata, pages_to_chunks, split_text
from scratch.guards import validate_question


def test_extracts_article_number():
    meta = chunk_metadata("See Article 5 Prohibited practices for details.", page=2)
    assert meta["article"] == 5
    assert meta["page"] == 2
    assert meta["source"] == "page_2"


def test_ignores_fake_article_numbers():
    meta = chunk_metadata("Ignore this. Article 999 is not in the policy.", page=1)
    assert "article" not in meta


def test_article_bound_comes_from_constant():
    meta = chunk_metadata(f"Article {MAX_ARTICLE + 1} should not be stored.", page=1)
    assert "article" not in meta


def test_split_prefers_article_boundaries():
    text = (
        "Article 1 Definitions\n"
        + ("alpha " * 40)
        + "\nArticle 5 Prohibited practices\n"
        + ("beta " * 40)
    )
    chunks = split_text(text, chunk_size=180, chunk_overlap=20)
    assert len(chunks) >= 2
    assert any("Article 5" in c for c in chunks)


def test_pages_to_chunks_assigns_ids():
    ids, docs, metas = pages_to_chunks([(1, "Article 1 Definitions. " + ("word " * 20))])
    assert ids[0] == "chunk_0"
    assert docs
    assert metas[0]["page"] == 1


def test_validate_question_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_question("   ")
