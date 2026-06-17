"""Input length guards — OWASP LLM05."""
from __future__ import annotations

import pytest

from app.guards import MAX_QUESTION_CHARS, validate_question
from app.rag import answer


def test_validate_question_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_question("   ")


def test_validate_question_rejects_oversized():
    with pytest.raises(ValueError, match="maximum length"):
        validate_question("x" * (MAX_QUESTION_CHARS + 1))


def test_validate_question_strips_whitespace():
    assert validate_question("  hello  ") == "hello"


def test_rag_rejects_oversized_question():
    with pytest.raises(ValueError, match="maximum length"):
        answer("x" * (MAX_QUESTION_CHARS + 1))
