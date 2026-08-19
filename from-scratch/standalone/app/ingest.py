"""Ingest path guard — OWASP LLM04."""
from __future__ import annotations

from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parents[1] / "corpus"
ALLOWED_SUFFIXES = {".pdf", ".txt"}


class IngestError(ValueError):
    """Bad corpus path."""


def resolve_corpus_path(raw: str | Path, corpus_dir: Path = CORPUS_DIR) -> Path:
    corpus = corpus_dir.resolve()
    path = Path(raw).expanduser().resolve()
    if not path.is_relative_to(corpus):
        raise IngestError(
            f"Corpus path must be inside {corpus}. Got {path}. "
            "This guard is OWASP LLM04 (ingest poisoning)."
        )
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_SUFFIXES))
        raise IngestError(f"Only {allowed} files are allowed, got {path.suffix!r}.")
    if not path.is_file():
        raise IngestError(f"Missing corpus file: {path}")
    return path
