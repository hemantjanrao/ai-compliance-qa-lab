"""Unit tests for advanced retrieval — no API keys."""
from __future__ import annotations

from app.retrieval.bm25_index import BM25Index
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.query_expansion import expand_queries, extract_article_filter


def test_reciprocal_rank_fusion_prefers_consensus():
    fused = reciprocal_rank_fusion(
        [
            ["a", "b", "c"],
            ["b", "a", "d"],
        ]
    )
    ids = [cid for cid, _ in fused]
    assert ids[0] in ("a", "b")
    assert "b" in ids[:2]


def test_bm25_search_finds_keyword_match():
    index = BM25Index.from_records(
        ids=["1", "2"],
        documents=[
            "Article 5 prohibits social scoring by public authorities.",
            "General-purpose AI models have transparency obligations.",
        ],
        metadatas=[{"source": "a"}, {"source": "b"}],
    )
    hits = index.search("social scoring prohibited", k=1)
    assert hits[0][0] == "1"


def test_expand_queries_adds_article_variant():
    queries = expand_queries("What does Article 6 say about high-risk systems?")
    assert any("Article 6" in q for q in queries)


def test_extract_article_filter():
    assert extract_article_filter("Look up Article 42") == 42
    assert extract_article_filter("What is prohibited?") is None
    assert extract_article_filter("Article 999") is None
