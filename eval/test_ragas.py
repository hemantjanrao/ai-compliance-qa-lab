"""RAGAS-based evaluation. Runs the four core RAG metrics on the golden dataset.

Run:
  pytest eval/test_ragas.py -v -m eval
"""
from __future__ import annotations

import pytest
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

from app.rag import answer
from eval.helpers import load_golden_rag, threshold
from eval.reporting import ReportCollector


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
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )
    print(f"\n[{provider}] RAGAS scores: {result}")

    for metric in ("faithfulness", "answer_relevancy", "context_precision", "context_recall"):
        value = float(result[metric])
        ReportCollector.set(f"ragas.{provider}.{metric}", value)
        floor = threshold(f"ragas.{metric}", 0.75)
        assert value >= floor, f"{metric} too low: {value} < {floor}"
