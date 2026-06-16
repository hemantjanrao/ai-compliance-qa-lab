"""Metamorphic testing for LLMs — paraphrase invariance.

Property: semantically equivalent questions should produce semantically equivalent answers.
We use embedding similarity instead of string match, because LLM outputs vary.

Run:
  pytest eval/test_metamorphic.py -v -m eval
"""
from __future__ import annotations

import pytest

from app.rag import answer
from eval.helpers import cosine, embed, threshold

PARAPHRASE_GROUPS = [
    [
        "What are the obligations for high-risk AI systems?",
        "Which requirements must high-risk AI systems comply with?",
        "List the duties that apply to high-risk AI systems under the EU AI Act.",
    ],
    [
        "When does the EU AI Act apply?",
        "From what date is the EU AI Act enforceable?",
        "What is the effective date of the AI Act?",
    ],
    [
        "Which AI practices are banned?",
        "What does the AI Act prohibit?",
        "List the prohibited uses of AI under the Regulation.",
    ],
]


@pytest.mark.eval
@pytest.mark.parametrize("provider", ["anthropic", "openai"])
@pytest.mark.parametrize("group", PARAPHRASE_GROUPS)
def test_paraphrase_invariance(group: list[str], provider: str):
    answers = [answer(q, provider=provider).answer for q in group]
    embeddings = [embed(a) for a in answers]
    sim_threshold = threshold("metamorphic.paraphrase_similarity", 0.78)
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            sim = cosine(embeddings[i], embeddings[j])
            assert sim >= sim_threshold, (
                f"[{provider}] Paraphrase invariance failed (sim={sim:.3f}):\n"
                f"Q1: {group[i]}\nA1: {answers[i][:200]}\n"
                f"Q2: {group[j]}\nA2: {answers[j][:200]}"
            )
