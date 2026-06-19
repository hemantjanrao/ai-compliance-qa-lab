"""Single source of truth for RAGAS, DeepEval, and promptfoo metric names.

Used by eval tests, eval/gate.py, and eval/thresholds.yaml documentation.
"""
from __future__ import annotations

# RAGAS — standard single-turn RAG metrics (eval/test_ragas.py)
RAGAS_METRICS: tuple[str, ...] = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "answer_correctness",
    "answer_similarity",
    "context_entity_recall",
    "context_relevance",
)

# DeepEval built-in RAG metrics — per provider (eval/test_deepeval.py)
DEEPEVAL_RAG_BUILTIN_METRICS: tuple[str, ...] = (
    "faithfulness",
    "answer_relevancy",
    "contextual_relevancy",
    "contextual_precision",
    "contextual_recall",
    "hallucination",
)

# DeepEval G-Eval rubrics — per provider (eval/test_deepeval.py)
DEEPEVAL_RAG_GEVAL_METRICS: tuple[str, ...] = (
    "citation_correctness",
    "refusal_correctness",
    "conciseness",
    "article_hallucination",
)

# DeepEval agent metrics (eval/agent/test_deepeval_agent.py)
DEEPEVAL_AGENT_METRICS: tuple[str, ...] = (
    "trajectory_quality",
    "tool_correctness",
    "task_completion",
)

DEEPEVAL_PROVIDER_METRICS: tuple[str, ...] = (
    *DEEPEVAL_RAG_BUILTIN_METRICS,
    *DEEPEVAL_RAG_GEVAL_METRICS,
)

# promptfoo aggregate metrics (eval/test_promptfoo.py)
PROMPTFOO_METRICS: tuple[str, ...] = (
    "pass_rate",
    "passed",
    "total",
    "failed",
)

PROVIDERS: tuple[str, ...] = ("anthropic", "openai")
