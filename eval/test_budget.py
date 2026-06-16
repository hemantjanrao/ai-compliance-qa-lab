"""Latency and cost budget tests — enforced in CI.

Run:
  pytest eval/test_budget.py -v -m eval
"""
from __future__ import annotations

import time

import pytest

from app.rag import answer
from eval.helpers import threshold
from eval.reporting import ReportCollector

SAMPLE_QUESTIONS = [
    "What is an AI system?",
    "Which AI practices are prohibited?",
    "What are the requirements for high-risk AI systems?",
    "When does the AI Act apply?",
    "What are the penalties for non-compliance?",
]


@pytest.mark.eval
@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_p95_latency(provider: str):
    latencies = []
    for q in SAMPLE_QUESTIONS * 2:  # 10 samples
        t0 = time.perf_counter()
        answer(q, provider=provider)
        latencies.append((time.perf_counter() - t0) * 1000)
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    print(f"\n[{provider}] p50={latencies[len(latencies)//2]:.0f}ms p95={p95:.0f}ms")
    ReportCollector.set(f"latency_p95_ms.{provider}", p95)
    max_p95 = threshold("latency.max_p95_ms", 4000)
    assert p95 < max_p95, f"[{provider}] p95 latency {p95:.0f}ms > budget {max_p95}ms"


@pytest.mark.eval
def test_cost_per_query_anthropic():
    r = answer("What is a high-risk AI system?", provider="anthropic")
    cost = (r.input_tokens / 1_000_000) * 1.0 + (r.output_tokens / 1_000_000) * 5.0
    print(f"\nAnthropic cost per query: ${cost:.5f}")
    ReportCollector.set("cost_per_query_usd.anthropic", cost)
    max_cost = threshold("cost.max_per_query_usd.anthropic", 0.01)
    assert cost < max_cost, f"Cost too high: ${cost:.5f}"


@pytest.mark.eval
def test_cost_per_query_openai():
    r = answer("What is a high-risk AI system?", provider="openai")
    cost = (r.input_tokens / 1_000_000) * 0.15 + (r.output_tokens / 1_000_000) * 0.60
    print(f"\nOpenAI cost per query: ${cost:.5f}")
    ReportCollector.set("cost_per_query_usd.openai", cost)
    max_cost = threshold("cost.max_per_query_usd.openai", 0.005)
    assert cost < max_cost, f"Cost too high: ${cost:.5f}"
