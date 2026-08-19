"""Ingest path guard — OWASP LLM04 (poisoned files at the source).

Session 2 step 1: we do not parse PDFs yet. We only answer
"is this path allowed?" If no, raise. Callers must not continue.
"""
from __future__ import annotations

from pathlib import Path

# This file is from-scratch/scratch/ingest.py
# parents[0] = scratch/, parents[1] = from-scratch/, / "corpus" = learner corpus
CORPUS_DIR = Path(__file__).resolve().parents[1] / "corpus"
ALLOWED_SUFFIXES = {".pdf", ".txt"}


class IngestError(ValueError):
    """Bad corpus path. Subclass of ValueError so `except ValueError` still catches it."""


def resolve_corpus_path(raw: str | Path, corpus_dir: Path = CORPUS_DIR) -> Path:
    """Return a safe absolute path inside corpus_dir, or raise IngestError.

    corpus_dir is an argument so tests can inject pytest's tmp_path.
    """
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
