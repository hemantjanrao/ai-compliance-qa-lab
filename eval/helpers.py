"""Shared eval helpers — embedding similarity, golden loaders, thresholds."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.embeddings import embed_text
from eval.reporting import load_thresholds

GOLDEN_RAG = Path("eval/datasets/golden.jsonl")
GOLDEN_AGENT = Path("eval/agent/golden_trajectories.jsonl")


def load_golden_rag() -> list[dict]:
    return [json.loads(line) for line in GOLDEN_RAG.read_text().splitlines() if line.strip()]


def load_golden_agent() -> list[dict]:
    return [json.loads(line) for line in GOLDEN_AGENT.read_text().splitlines() if line.strip()]


def embed(text: str) -> np.ndarray:
    return embed_text(text)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def threshold(path: str, default: float) -> float:
    """Read nested threshold like 'metamorphic.paraphrase_similarity'."""
    node: object = load_thresholds()
    for part in path.split("."):
        if not isinstance(node, dict):
            return default
        node = node.get(part, default)
    return float(node) if node is not None else default
