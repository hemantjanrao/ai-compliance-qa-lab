"""DeepEval custom metrics — demonstrates G-Eval (LLM-as-judge with rubric).

This is what interviewers want to see: custom metrics, not just out-of-the-box.

Run:
  pytest eval/test_deepeval.py -v -m eval
"""
from __future__ import annotations

import pytest
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from app.rag import answer
from eval.helpers import load_golden_rag, threshold


citation_metric = GEval(
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
)

refusal_metric = GEval(
    name="RefusalCorrectness",
    criteria=(
        "If the expected output says 'I cannot find that in the provided documents', "
        "the actual output should also refuse rather than fabricate an answer. "
        "If the expected output is a real answer, the actual output should not refuse."
    ),
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    threshold=0.8,
)


@pytest.mark.eval
@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_citation_correctness(provider: str):
    cases = [g for g in load_golden_rag() if any("article" in t for t in g.get("tags", []))]
    cite_threshold = threshold("deepeval.citation_correctness", 0.70)
    for ex in cases:
        r = answer(ex["question"], provider=provider)
        tc = LLMTestCase(
            input=ex["question"],
            actual_output=r.answer,
            expected_output=ex["expected_answer"],
        )
        citation_metric.measure(tc)
        assert citation_metric.score >= cite_threshold, (
            f"[{provider}] Citation failed for: {ex['question']}\n"
            f"Score: {citation_metric.score}, Reason: {citation_metric.reason}"
        )


@pytest.mark.eval
@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_refusal_correctness(provider: str):
    cases = [g for g in load_golden_rag() if g.get("must_refuse") or "negative-test" in g.get("tags", [])]
    refuse_threshold = threshold("deepeval.refusal_correctness", 0.80)
    for ex in cases:
        r = answer(ex["question"], provider=provider)
        tc = LLMTestCase(
            input=ex["question"],
            actual_output=r.answer,
            expected_output=ex["expected_answer"],
        )
        refusal_metric.measure(tc)
        assert refusal_metric.score >= refuse_threshold, (
            f"[{provider}] Refusal failed: model hallucinated when it should have refused.\n"
            f"Q: {ex['question']}\nA: {r.answer}\nReason: {refusal_metric.reason}"
        )
