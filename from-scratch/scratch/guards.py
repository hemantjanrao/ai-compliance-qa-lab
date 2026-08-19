"""Input guards — OWASP LLM05 (DoS via oversized prompts)."""
from __future__ import annotations

import os

MAX_QUESTION_CHARS = int(os.getenv("MAX_QUESTION_CHARS", "4000"))


def validate_question(question: str) -> str:
    """Return a cleaned question, or raise ValueError before any retrieval/LLM call."""
    q = question.strip()
    if not q:
        raise ValueError("Question must not be empty.")
    if len(q) > MAX_QUESTION_CHARS:
        raise ValueError(
            f"Question exceeds maximum length ({MAX_QUESTION_CHARS} characters)."
        )
    return q
