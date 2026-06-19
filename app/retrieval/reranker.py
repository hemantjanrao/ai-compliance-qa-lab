"""Cross-encoder re-ranking for retrieval candidates."""
from __future__ import annotations

from functools import lru_cache

from app.retrieval.config import rerank_model_name

_reranker = None


@lru_cache(maxsize=1)
def _get_cross_encoder():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(rerank_model_name())


def rerank(
    query: str,
    candidates: list[tuple[str, str]],
    k: int,
) -> list[tuple[str, float]]:
    """Re-rank (chunk_id, text) pairs. Returns (chunk_id, score) descending."""
    if not candidates:
        return []
    if len(candidates) == 1:
        return [(candidates[0][0], 1.0)]

    model = _get_cross_encoder()
    pairs = [(query, text) for _, text in candidates]
    scores = model.predict(pairs)
    ranked = sorted(
        zip((cid for cid, _ in candidates), scores),
        key=lambda item: float(item[1]),
        reverse=True,
    )
    return ranked[:k]
