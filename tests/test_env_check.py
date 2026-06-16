"""Unit tests for env / API key checks."""
from __future__ import annotations

import os

from app.env_check import (
    anthropic_configured,
    default_llm_provider,
    format_api_error,
    is_placeholder_key,
    openai_configured,
)


def test_placeholder_detection():
    assert is_placeholder_key("sk-ant-...")
    assert is_placeholder_key("")
    assert not is_placeholder_key("sk-ant-api03-realkeywithsufficientlength")


def test_anthropic_configured(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-abcdefghijklmnopqrstuvwxyz123456")
    assert anthropic_configured()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-...")
    assert not anthropic_configured()


def test_default_provider_prefers_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-abcdefghijklmnopqrstuvwxyz123456")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890")
    assert default_llm_provider() == "anthropic"


def test_format_quota_error():
    class RateLimitError(Exception):
        pass

    msg = format_api_error(
        RateLimitError(
            "Error code: 429 - insufficient_quota - You exceeded your current quota"
        )
    )
    assert "quota exhausted" in msg.lower()


def test_format_auth_error():
    class AuthenticationError(Exception):
        pass

    msg = format_api_error(AuthenticationError("invalid x-api-key"))
    assert "Invalid API key" in msg
