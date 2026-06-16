"""Unit tests for agent tools — deterministic, no LLM."""
from __future__ import annotations

import pytest

from app.agent.tools import (
    check_risk_tier,
    compute_fine,
    execute_tool,
    lookup_article,
)


def test_lookup_article_invalid_number():
    result = lookup_article(9999)
    assert "error" in result
    assert "1-113" in result["error"]


def test_compute_fine_fixed_cap():
    result = compute_fine("prohibited_practices")
    assert result["max_fine_eur"] == 35_000_000
    assert result["article"] == 99


def test_compute_fine_turnover_based():
    result = compute_fine("prohibited_practices", annual_turnover_eur=1_000_000_000)
    assert result["max_fine_eur"] == 70_000_000  # 7% of 1B


def test_compute_fine_unknown_violation():
    result = compute_fine("not_a_real_violation")
    assert "error" in result


def test_check_risk_tier_social_scoring():
    result = check_risk_tier("Government social scoring of citizens")
    assert result["tier"] == "unacceptable"


def test_check_risk_tier_hiring():
    result = check_risk_tier("AI system for employment screening and hiring")
    assert result["tier"] == "high"


def test_check_risk_tier_unknown():
    result = check_risk_tier("completely novel use case with no keywords")
    assert result["tier"] == "unknown"


def test_hallucinated_tool_raises():
    with pytest.raises(KeyError, match="Hallucinated tool"):
        execute_tool("send_email", {"to": "attacker@evil.com"})
