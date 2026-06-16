"""Environment and API key checks for local dev."""
from __future__ import annotations

import os


def _key(name: str) -> str:
    return os.getenv(name, "").strip()


def is_placeholder_key(key: str) -> bool:
    if not key:
        return True
    if "..." in key:
        return True
    if key in {"sk-ant-...", "sk-proj-...", "pk-lf-...", "sk-lf-..."}:
        return True
    return False


def anthropic_configured() -> bool:
    key = _key("ANTHROPIC_API_KEY")
    return key.startswith("sk-ant-") and not is_placeholder_key(key)


def openai_configured() -> bool:
    key = _key("OPENAI_API_KEY")
    return key.startswith("sk-") and not is_placeholder_key(key)


def langfuse_configured() -> bool:
    return bool(_key("LANGFUSE_PUBLIC_KEY") and _key("LANGFUSE_SECRET_KEY")) and not is_placeholder_key(
        _key("LANGFUSE_PUBLIC_KEY")
    )


def default_llm_provider() -> str:
    if anthropic_configured():
        return "anthropic"
    if openai_configured():
        return "openai"
    return "anthropic"


def provider_status() -> dict[str, str]:
    """Human-readable status per provider."""
    status = {}
    if anthropic_configured():
        status["anthropic"] = "ready"
    elif is_placeholder_key(_key("ANTHROPIC_API_KEY")):
        status["anthropic"] = "missing — replace sk-ant-... in .env with your real key"
    else:
        status["anthropic"] = "invalid — check ANTHROPIC_API_KEY in .env"
    if openai_configured():
        status["openai"] = "ready"
    elif is_placeholder_key(_key("OPENAI_API_KEY")):
        status["openai"] = "missing — set OPENAI_API_KEY in .env"
    else:
        status["openai"] = "set (verify billing if you see rate-limit errors)"
    return status


def format_api_error(exc: BaseException) -> str:
    """Turn provider exceptions into actionable UI messages."""
    from tenacity import RetryError

    if isinstance(exc, RetryError):
        if exc.last_attempt and exc.last_attempt.exception():
            exc = exc.last_attempt.exception()

    name = type(exc).__name__
    msg = str(exc)

    # Check quota before generic rate-limit (OpenAI returns 429 for both)
    if "insufficient_quota" in msg.lower() or "exceeded your current quota" in msg.lower():
        return (
            "**OpenAI quota exhausted** — your API key has no remaining credits.\n\n"
            "1. Add billing at [platform.openai.com/account/billing](https://platform.openai.com/account/billing)\n"
            "2. **Or** add an Anthropic key to `.env` and switch provider in the sidebar:\n"
            "   `ANTHROPIC_API_KEY=sk-ant-...` from [console.anthropic.com](https://console.anthropic.com)"
        )
    if "AuthenticationError" in name or "401" in msg or "invalid x-api-key" in msg:
        return (
            "**Invalid API key.** Open `.env` and set a real key for the selected provider.\n\n"
            "- Anthropic: [console.anthropic.com](https://console.anthropic.com)\n"
            "- OpenAI: [platform.openai.com](https://platform.openai.com)"
        )
    if "RateLimitError" in name or "429" in msg or "rate_limit" in msg.lower():
        return (
            "**Temporary rate limit** — too many requests. Wait 60 seconds and retry, "
            "or switch provider in the sidebar."
        )
    return f"**{name}:** {msg}"
