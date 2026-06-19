"""Unit tests for eval gate logic — no API keys."""
from __future__ import annotations

from eval.gate import compare_reports


def test_gate_passes_when_metrics_stable():
    baseline = {
        "ragas": {
            "anthropic": {"faithfulness": 0.85, "answer_relevancy": 0.85, "context_precision": 0.78, "context_recall": 0.78},
            "openai": {"faithfulness": 0.85, "answer_relevancy": 0.85, "context_precision": 0.78, "context_recall": 0.78},
        },
        "latency_p95_ms": {"anthropic": 3000, "openai": 2800},
        "adversarial": {"rag_passed": True, "agent_passed": True},
    }
    current = {
        "ragas": {
            "anthropic": {"faithfulness": 0.84, "answer_relevancy": 0.84, "context_precision": 0.77, "context_recall": 0.77},
            "openai": {"faithfulness": 0.83, "answer_relevancy": 0.83, "context_precision": 0.76, "context_recall": 0.76},
        },
        "latency_p95_ms": {"anthropic": 3100, "openai": 2900},
        "adversarial": {"rag_passed": True, "agent_passed": True},
    }
    result = compare_reports(baseline, current)
    assert result.passed


def test_gate_fails_on_large_faithfulness_drop():
    baseline = {
        "ragas": {
            "anthropic": {"faithfulness": 0.90, "answer_relevancy": 0.90, "context_precision": 0.80, "context_recall": 0.80},
            "openai": {},
        },
        "latency_p95_ms": {},
        "adversarial": {},
    }
    current = {
        "ragas": {
            "anthropic": {"faithfulness": 0.80, "answer_relevancy": 0.90, "context_precision": 0.80, "context_recall": 0.80},
            "openai": {},
        },
        "latency_p95_ms": {},
        "adversarial": {},
    }
    result = compare_reports(baseline, current, max_metric_drop=0.05)
    assert not result.passed
    assert any("faithfulness" in f.check for f in result.failures)


def test_gate_fails_on_latency_regression():
    baseline = {
        "ragas": {"anthropic": {}, "openai": {}},
        "latency_p95_ms": {"anthropic": 2000},
        "adversarial": {},
    }
    current = {
        "ragas": {"anthropic": {}, "openai": {}},
        "latency_p95_ms": {"anthropic": 3000},
        "adversarial": {},
    }
    result = compare_reports(baseline, current, max_latency_increase=0.30)
    assert not result.passed
    assert any("latency" in f.check for f in result.failures)


def test_gate_fails_on_promptfoo_pass_rate_regression():
    baseline = {
        "ragas": {"anthropic": {}, "openai": {}},
        "promptfoo": {"pass_rate": 0.90},
        "latency_p95_ms": {},
        "adversarial": {},
    }
    current = {
        "ragas": {"anthropic": {}, "openai": {}},
        "promptfoo": {"pass_rate": 0.80},
        "latency_p95_ms": {},
        "adversarial": {},
    }
    result = compare_reports(baseline, current, max_metric_drop=0.05)
    assert not result.passed
    assert any("promptfoo" in f.check for f in result.failures)


def test_gate_fails_on_deepeval_floor_breach():
    baseline = {
        "ragas": {"anthropic": {}, "openai": {}},
        "deepeval": {"anthropic": {"citation_correctness": 0.85}},
        "latency_p95_ms": {},
        "adversarial": {},
    }
    current = {
        "ragas": {"anthropic": {}, "openai": {}},
        "deepeval": {"anthropic": {"citation_correctness": 0.65}},
        "latency_p95_ms": {},
        "adversarial": {},
    }
    result = compare_reports(baseline, current)
    assert not result.passed
    assert any("deepeval" in f.check for f in result.failures)
