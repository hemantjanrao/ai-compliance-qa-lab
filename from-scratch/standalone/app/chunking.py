"""Split long text into overlapping chunks and tag article numbers.

Chunking is the highest-leverage RAG knob. If chunks are wrong, later
metrics look like "the model is bad" when ingest was the bug.

This is a small recursive splitter: try separators in order. We put
"\\nArticle " first so policy text prefers to break at article boundaries.
"""
from __future__ import annotations

import os
import re

MAX_ARTICLE = int(os.getenv("MAX_ARTICLE", "20"))
_ARTICLE_RE = re.compile(r"\bArticle\s+(\d{1,3})\b")
DEFAULT_SEPARATORS = ("\nArticle ", "\n\n", "\n", ". ", " ")


def get_chunk_size() -> int:
    return int(os.getenv("CHUNK_SIZE", "2000"))


def get_chunk_overlap() -> int:
    return int(os.getenv("CHUNK_OVERLAP", "100"))


def split_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    separators: tuple[str, ...] = DEFAULT_SEPARATORS,
) -> list[str]:
    size = get_chunk_size() if chunk_size is None else chunk_size
    overlap = get_chunk_overlap() if chunk_overlap is None else chunk_overlap
    if size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size")
    pieces = _split_recursive(text.strip(), size, list(separators))
    return _apply_overlap(pieces, size, overlap)


# Tests may import this name; keep it as an alias of split_text.
chunk_text = split_text


def _split_recursive(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text else []
    if not separators:
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    sep, rest = separators[0], separators[1:]
    parts = text.split(sep) if sep else list(text)
    out: list[str] = []
    buf = ""
    for i, part in enumerate(parts):
        # Re-attach the separator except for the first piece (same as LangChain).
        piece = part if i == 0 or not sep else f"{sep}{part}"
        candidate = buf + piece
        if len(candidate) <= chunk_size:
            buf = candidate
            continue
        if buf:
            out.extend(_split_recursive(buf, chunk_size, rest))
            buf = piece
        else:
            out.extend(_split_recursive(piece, chunk_size, rest))
            buf = ""
    if buf:
        out.extend(_split_recursive(buf, chunk_size, rest))
    return [p for p in out if p]


def _apply_overlap(pieces: list[str], chunk_size: int, overlap: int) -> list[str]:
    if overlap == 0 or len(pieces) <= 1:
        return pieces
    merged: list[str] = []
    prev_tail = ""
    for piece in pieces:
        combined = (prev_tail + piece) if prev_tail else piece
        if len(combined) > chunk_size + overlap:
            combined = combined[-chunk_size:]
        merged.append(combined)
        prev_tail = combined[-overlap:]
    return merged


def chunk_metadata(page_content: str, page: int) -> dict:
    """Metadata is a retrieval lever. Later: where={"article": 5}."""
    meta: dict = {"source": f"page_{page}", "page": page}
    match = _ARTICLE_RE.search(page_content)
    if not match:
        return meta
    article = int(match.group(1))
    if 1 <= article <= MAX_ARTICLE:
        meta["article"] = article
    return meta


def pages_to_chunks(pages: list[tuple[int, str]]) -> tuple[list[str], list[str], list[dict]]:
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []
    n = 0
    for page_num, text in pages:
        for piece in split_text(text):
            ids.append(f"chunk_{n}")
            documents.append(piece)
            metadatas.append(chunk_metadata(piece, page_num))
            n += 1
    if not documents:
        raise ValueError("Splitter produced zero chunks.")
    return ids, documents, metadatas
