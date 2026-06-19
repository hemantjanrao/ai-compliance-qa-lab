"""Retrieval orchestration — basic vs advanced (hybrid + rerank)."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import chromadb

from app.embeddings import get_chroma_embedding_function
from app.observability import trace
from app.retrieval.types import RetrievedChunk
from app.retrieval.bm25_index import BM25Index
from app.retrieval.config import (
    RetrievalMode,
    bm25_index_path,
    candidate_multiplier,
    get_retrieval_mode,
)
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.query_expansion import expand_queries, extract_article_filter
from app.retrieval.reranker import rerank

if TYPE_CHECKING:
    from chromadb.api.models.Collection import Collection


def _get_collection() -> Collection:
    client = chromadb.PersistentClient(path=os.getenv("CHROMA_PATH", "./chroma_db"))
    embed_fn = get_chroma_embedding_function()
    return client.get_or_create_collection(
        name=os.getenv("COLLECTION_NAME", "eu_ai_act"),
        embedding_function=embed_fn,
    )


def _vector_search(coll: Collection, query: str, k: int) -> list[tuple[str, float]]:
    res = coll.query(query_texts=[query], n_results=k)
    ids = res["ids"][0]
    distances = res["distances"][0]
    return list(zip(ids, distances))


def _chunks_from_ids(
    coll: Collection,
    ranked: list[tuple[str, float]],
    bm25: BM25Index | None,
) -> list[RetrievedChunk]:
    if not ranked:
        return []

    chunk_ids = [cid for cid, _ in ranked]
    score_by_id = {cid: score for cid, score in ranked}
    fetched = coll.get(ids=chunk_ids, include=["documents", "metadatas"])
    by_id = {
        i: (doc, meta)
        for i, doc, meta in zip(fetched["ids"], fetched["documents"], fetched["metadatas"])
    }

    chunks: list[RetrievedChunk] = []
    for cid in chunk_ids:
        if cid not in by_id:
            continue
        doc, meta = by_id[cid]
        meta = meta or {}
        if bm25:
            bm25_chunk = bm25.get(cid)
            if bm25_chunk:
                doc = bm25_chunk.text
                meta = bm25_chunk.metadata
        # Lower distance = better; invert fused/rerank scores for API compatibility
        score = score_by_id[cid]
        distance = 1.0 / (1.0 + score) if score > 0 else 1.0
        chunks.append(
            RetrievedChunk(
                text=doc,
                source=meta.get("source", "unknown"),
                distance=distance,
            )
        )
    return chunks


def retrieve_basic(question: str, k: int, coll: Collection | None = None) -> list[RetrievedChunk]:
    coll = coll or _get_collection()
    res = coll.query(query_texts=[question], n_results=k)
    chunks = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        chunks.append(RetrievedChunk(text=doc, source=meta.get("source", "unknown"), distance=dist))
    return chunks


def retrieve_advanced(question: str, k: int, coll: Collection | None = None) -> list[RetrievedChunk]:
    coll = coll or _get_collection()
    bm25 = BM25Index.load(bm25_index_path())
    queries = expand_queries(question)
    article = extract_article_filter(question)

    candidate_k = max(k * candidate_multiplier(), k)
    ranked_lists: list[list[str]] = []

    with trace(
        "retrieve.hybrid",
        input={"queries": queries, "k": k, "candidate_k": candidate_k, "article_filter": article},
        as_type="retriever",
    ):
        for q in queries:
            where = {"article": article} if article is not None else None
            try:
                res = coll.query(query_texts=[q], n_results=candidate_k, where=where)
            except Exception:
                res = coll.query(query_texts=[q], n_results=candidate_k)
            ranked_lists.append(res["ids"][0])

            if bm25 is not None:
                bm25_hits = bm25.search(q, candidate_k)
                ranked_lists.append([cid for cid, _ in bm25_hits])

        fused = reciprocal_rank_fusion(ranked_lists)[: max(k * 2, k)]

        candidate_ids = [cid for cid, _ in fused]
        candidate_texts: list[tuple[str, str]] = []
        if bm25 is not None:
            for cid in candidate_ids:
                chunk = bm25.get(cid)
                if chunk:
                    candidate_texts.append((cid, chunk.text))
        else:
            fetched = coll.get(ids=candidate_ids, include=["documents"])
            for cid, doc in zip(fetched["ids"], fetched["documents"]):
                candidate_texts.append((cid, doc))

        reranked = rerank(question, candidate_texts, k=k)
        if not reranked:
            reranked = fused[:k]

    return _chunks_from_ids(coll, reranked, bm25)


def retrieve_chunks(
    question: str,
    k: int = 5,
    *,
    mode: RetrievalMode | None = None,
) -> list[RetrievedChunk]:
    mode = mode or get_retrieval_mode()
    if mode == RetrievalMode.BASIC:
        return retrieve_basic(question, k)
    return retrieve_advanced(question, k)
