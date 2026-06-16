"""LLM provider abstraction. Swap providers via config without touching call sites."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from anthropic import Anthropic
from openai import OpenAI
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


def _is_retryable(exc: BaseException) -> bool:
    """Don't retry auth failures or exhausted quota — they won't succeed on retry."""
    msg = str(exc).lower()
    if "insufficient_quota" in msg or "exceeded your current quota" in msg:
        return False
    if "invalid x-api-key" in msg or "authentication" in msg.lower():
        return False
    return True


_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=30),
    retry=retry_if_exception(_is_retryable),
)

ProviderName = Literal["anthropic", "openai"]


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: ProviderName


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system: str, user: str, max_tokens: int = 1024) -> LLMResponse: ...


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str | None = None):
        self.client = Anthropic()
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    @_retry
    def generate(self, system: str, user: str, max_tokens: int = 1024) -> LLMResponse:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return LLMResponse(
            text=resp.content[0].text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            model=self.model,
            provider="anthropic",
        )


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str | None = None):
        self.client = OpenAI()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    @_retry
    def generate(self, system: str, user: str, max_tokens: int = 1024) -> LLMResponse:
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            input_tokens=resp.usage.prompt_tokens,
            output_tokens=resp.usage.completion_tokens,
            model=self.model,
            provider="openai",
        )


def get_provider(name: ProviderName) -> LLMProvider:
    if name == "anthropic":
        return AnthropicProvider()
    if name == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unknown provider: {name}")
