"""RAGAS evaluation — all standard single-turn RAG metrics on the golden dataset.

Metrics: faithfulness, answer_relevancy, context_precision, context_recall,
answer_correctness, answer_similarity, context_entity_recall, context_relevance.

Run:
  pytest eval/test_ragas.py -v -m eval
  pytest eval/test_ragas.py -v -m eval -k anthropic
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    ContextRelevance,
    answer_correctness,
    answer_relevancy,
    answer_similarity,
    context_entity_recall,
    context_precision,
    context_recall,
    faithfulness,
)

from app.rag import answer
from eval.helpers import load_golden_rag, threshold
from eval.metrics_registry import RAGAS_METRICS
from eval.ragas_config import get_ragas_embeddings, get_ragas_llm
from eval.reporting import ReportCollector

_RAGAS_METRIC_OBJECTS = [
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    answer_correctness,
    answer_similarity,
    context_entity_recall,
    ContextRelevance(),
]


@pytest.mark.eval
@pytest.mark.slow
def test_rag_metrics_anthropic():
    _run_metrics(provider="anthropic")


@pytest.mark.eval
@pytest.mark.slow
def test_rag_metrics_openai():
    _run_metrics(provider="openai")


def _run_metrics(provider: str) -> None:
    golden = load_golden_rag()
    questions, answers, contexts, references = [], [], [], []
    for ex in golden:
        r = answer(ex["question"], provider=provider)
        questions.append(ex["question"])
        answers.append(r.answer)
        contexts.append([c.text for c in r.chunks])
        references.append(ex["expected_answer"])

    ds = Dataset.from_dict(
        {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": references,
        }
    )
    result = evaluate(
        ds,
        metrics=_RAGAS_METRIC_OBJECTS,
        llm=get_ragas_llm(),
        embeddings=get_ragas_embeddings(),
    )
    print(f"\n[{provider}] RAGAS scores: {result}")

    df = result.to_pandas()
    for metric in RAGAS_METRICS:
        if metric not in df.columns:
            pytest.fail(f"{metric} missing from RAGAS output")
        value = float(np.nanmean(df[metric]))
        nan_count = int(df[metric].isna().sum())
        if nan_count:
            print(f"  warning: {metric} had {nan_count}/{len(df)} NaN scores")
        if math.isnan(value):
            pytest.fail(
                f"{metric} is all NaN — RAGAS judge failed on every row. "
                "Check ANTHROPIC_API_KEY and eval/ragas_config.py."
            )
        ReportCollector.set(f"ragas.{provider}.{metric}", value)
        floor = threshold(f"ragas.{metric}", 0.70)
        assert value >= floor, f"{metric} too low: {value:.3f} < {floor}"
