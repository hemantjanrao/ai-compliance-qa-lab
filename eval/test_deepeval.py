"""DeepEval — all applicable RAG metrics (built-in + G-Eval rubrics).

Built-in: faithfulness, answer_relevancy, contextual_relevancy, contextual_precision,
contextual_recall, hallucination.

G-Eval: citation_correctness, refusal_correctness, conciseness, article_hallucination.

Run:
  pytest eval/test_deepeval.py -v -m eval
"""
from __future__ import annotations

import pytest

from app.rag import answer
from eval.deepeval_helpers import (
    RagEvalRow,
    build_llm_test_case,
    builtin_rag_metrics,
    filter_cases_for_geval,
    geval_rag_metrics,
    mean_score,
)
from eval.helpers import load_golden_rag, threshold
from eval.metrics_registry import DEEPEVAL_RAG_BUILTIN_METRICS, DEEPEVAL_RAG_GEVAL_METRICS
from eval.reporting import ReportCollector


def _load_rows(provider: str) -> list[RagEvalRow]:
    return [
        RagEvalRow(
            question=ex["question"],
            expected_answer=ex["expected_answer"],
            must_refuse=bool(ex.get("must_refuse")),
            tags=ex.get("tags", []),
            result=answer(ex["question"], provider=provider),
        )
        for ex in load_golden_rag()
    ]


@pytest.mark.eval
@pytest.mark.slow
@pytest.mark.parametrize("provider", ["anthropic", "openai"])
@pytest.mark.parametrize("metric_name", DEEPEVAL_RAG_BUILTIN_METRICS)
def test_deepeval_builtin_rag_metrics(provider: str, metric_name: str):
    rows = _load_rows(provider)
    metric = builtin_rag_metrics()[metric_name]
    floor = threshold(f"deepeval.{metric_name}", 0.70)
    scores: list[float] = []

    for row in rows:
        tc = build_llm_test_case(row)
        metric.measure(tc)
        scores.append(metric.score)
        assert metric.score >= floor, (
            f"[{provider}] {metric_name} failed for: {row.question}\n"
            f"Score: {metric.score}, Reason: {getattr(metric, 'reason', '')}\n"
            f"Answer: {row.result.answer[:300]}"
        )

    ReportCollector.set(f"deepeval.{provider}.{metric_name}", mean_score(scores))


@pytest.mark.eval
@pytest.mark.slow
@pytest.mark.parametrize("provider", ["anthropic", "openai"])
@pytest.mark.parametrize("metric_name", DEEPEVAL_RAG_GEVAL_METRICS)
def test_deepeval_geval_rag_metrics(provider: str, metric_name: str):
    rows = _load_rows(provider)
    cases = filter_cases_for_geval(metric_name, rows)
    if not cases:
        pytest.skip(f"No golden cases for {metric_name}")

    metric = geval_rag_metrics()[metric_name]
    floor = threshold(f"deepeval.{metric_name}", 0.70)
    scores: list[float] = []

    for row in cases:
        tc = build_llm_test_case(row)
        metric.measure(tc)
        scores.append(metric.score)
        assert metric.score >= floor, (
            f"[{provider}] {metric_name} failed for: {row.question}\n"
            f"Score: {metric.score}, Reason: {metric.reason}\n"
            f"Answer: {row.result.answer[:300]}"
        )

    ReportCollector.set(f"deepeval.{provider}.{metric_name}", mean_score(scores))
