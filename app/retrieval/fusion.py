"""Reciprocal Rank Fusion for hybrid retrieval."""
from __future__ import annotations


def reciprocal_rank_fusion(
    ranked_ids: list[list[str]],
    *,
    rrf_k: int = 60,
) -> list[tuple[str, float]]:
    """Merge ranked chunk-id lists. Higher score is better."""
    scores: dict[str, float] = {}
    for ranking in ranked_ids:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank + 1)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
