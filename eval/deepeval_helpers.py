"""Shared helpers for DeepEval metric runs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
    GEval,
    HallucinationMetric,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from app.rag import RAGResult


@dataclass
class RagEvalRow:
    question: str
    expected_answer: str
    must_refuse: bool
    tags: list[str]
    result: RAGResult


def build_llm_test_case(row: RagEvalRow) -> LLMTestCase:
    retrieval_context = [c.text for c in row.result.chunks]
    return LLMTestCase(
        input=row.question,
        actual_output=row.result.answer,
        expected_output=row.expected_answer,
        retrieval_context=retrieval_context,
        context=[row.expected_answer],
    )


def builtin_rag_metrics() -> dict[str, Any]:
    """DeepEval built-in metrics applicable to RAG (async off for pytest stability)."""
    common = dict(threshold=0.7, async_mode=False)
    return {
        "faithfulness": FaithfulnessMetric(**common),
        "answer_relevancy": AnswerRelevancyMetric(**common),
        "contextual_relevancy": ContextualRelevancyMetric(**common),
        "contextual_precision": ContextualPrecisionMetric(**common),
        "contextual_recall": ContextualRecallMetric(**common),
        "hallucination": HallucinationMetric(threshold=0.5, async_mode=False),
    }


def geval_rag_metrics() -> dict[str, GEval]:
    return {
        "citation_correctness": GEval(
            name="CitationCorrectness",
            criteria=(
                "Determine whether the actual output correctly cites EU AI Act articles when the "
                "expected output contains article references. Penalize hallucinated article numbers."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
            ],
            threshold=0.7,
        ),
        "refusal_correctness": GEval(
            name="RefusalCorrectness",
            criteria=(
                "If the expected output says 'I cannot find that in the provided documents', "
                "the actual output should also refuse rather than fabricate an answer. "
                "If the expected output is a real answer, the actual output should not refuse."
            ),
            evaluation_params=[
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
            ],
            threshold=0.8,
        ),
        "conciseness": GEval(
            name="Conciseness",
            criteria=(
                "Score whether the actual output is appropriately concise for a compliance answer. "
                "Penalize excessive verbosity when the expected answer is short. "
                "Do not penalize necessary legal detail or article citations."
            ),
            evaluation_params=[
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
            ],
            threshold=0.7,
        ),
        "article_hallucination": GEval(
            name="ArticleHallucination",
            criteria=(
                "Penalize citing specific EU AI Act Article numbers that are not supported by "
                "the expected output or question context. Score highly when article references "
                "match the expected answer or when no articles are cited unnecessarily."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
            ],
            threshold=0.7,
        ),
    }


def mean_score(scores: list[float]) -> float:
    return sum(scores) / len(scores) if scores else 0.0


def filter_cases_for_geval(metric_name: str, rows: list[RagEvalRow]) -> list[RagEvalRow]:
    if metric_name == "citation_correctness":
        return [r for r in rows if any("article" in t for t in r.tags)]
    if metric_name == "refusal_correctness":
        return [r for r in rows if r.must_refuse or "negative-test" in r.tags]
    return rows
