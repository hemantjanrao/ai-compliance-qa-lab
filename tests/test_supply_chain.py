"""Supply-chain guardrails — OWASP LLM03."""
from __future__ import annotations

from pathlib import Path


def test_langchain_and_ragas_pinned_in_pyproject():
    """Ragas breaks on langchain 0.4+; pin documents supply-chain risk control."""
    text = Path("pyproject.toml").read_text()
    assert "langchain>=0.3,<0.4" in text
    assert "ragas>=0.3.9,<0.4" in text
    assert "langchain-community>=0.3.20,<0.4" in text


def test_dev_dependencies_include_eval_stack():
    text = Path("pyproject.toml").read_text()
    for pkg in ("deepeval", "ragas", "playwright", "promptfoo"):
        assert pkg in text
