"""Lightweight query expansion — no extra LLM calls."""
from __future__ import annotations

import re

_ARTICLE_RE = re.compile(r"\barticle\s+(\d{1,3})\b", re.IGNORECASE)


def expand_queries(question: str) -> list[str]:
    """Return deduplicated query variants for multi-query retrieval."""
    queries = [question.strip()]
    seen = {q.lower() for q in queries}

    match = _ARTICLE_RE.search(question)
    if match:
        article_q = f"Article {match.group(1)}"
        if article_q.lower() not in seen:
            queries.append(article_q)
            seen.add(article_q.lower())

    lowered = question.lower()
    if "prohibit" in lowered and "article 5" not in lowered:
        extra = "Article 5 prohibited AI practices"
        if extra.lower() not in seen:
            queries.append(extra)

    if "high-risk" in lowered or "high risk" in lowered:
        extra = "high-risk AI systems requirements Annex III"
        if extra.lower() not in seen:
            queries.append(extra)

    return queries


def extract_article_filter(question: str) -> int | None:
    """Optional metadata filter when user asks about a specific Article."""
    match = _ARTICLE_RE.search(question)
    if not match:
        return None
    num = int(match.group(1))
    return num if 1 <= num <= 113 else None
