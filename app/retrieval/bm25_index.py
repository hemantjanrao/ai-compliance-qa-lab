"""BM25 sparse index — persisted alongside Chroma for hybrid search."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"\w+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class BM25Chunk:
    chunk_id: str
    text: str
    metadata: dict


class BM25Index:
    def __init__(self, chunks: list[BM25Chunk]) -> None:
        self.chunks = chunks
        self._by_id = {c.chunk_id: c for c in chunks}
        self._bm25 = BM25Okapi([tokenize(c.text) for c in chunks])

    @classmethod
    def from_records(
        cls,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
    ) -> BM25Index:
        chunks = [
            BM25Chunk(chunk_id=i, text=d, metadata=m)
            for i, d, m in zip(ids, documents, metadatas)
        ]
        return cls(chunks)

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        if not self.chunks:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(
            ((self.chunks[i].chunk_id, float(scores[i])) for i in range(len(self.chunks))),
            key=lambda item: item[1],
            reverse=True,
        )
        return ranked[:k]

    def get(self, chunk_id: str) -> BM25Chunk | None:
        return self._by_id.get(chunk_id)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ids": [c.chunk_id for c in self.chunks],
            "documents": [c.text for c in self.chunks],
            "metadatas": [c.metadata for c in self.chunks],
        }
        path.write_text(json.dumps(payload))

    @classmethod
    def load(cls, path: Path) -> BM25Index | None:
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return cls.from_records(
            ids=data["ids"],
            documents=data["documents"],
            metadatas=data["metadatas"],
        )
