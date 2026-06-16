"""Unit tests for RAG prompt assembly."""
from __future__ import annotations

from app.rag import USER_TEMPLATE


def test_user_template_includes_context_and_question():
    rendered = USER_TEMPLATE.format(context="Article 5 text", question="What is prohibited?")
    assert "Article 5 text" in rendered
    assert "What is prohibited?" in rendered
    assert "Context from EU AI Act" in rendered
