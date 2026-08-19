"""Ingest path guard — OWASP LLM04. No embedding model, no Chroma."""
from __future__ import annotations

from pathlib import Path

import pytest

from scratch.ingest import IngestError, resolve_corpus_path


def test_missing_file_is_a_readable_error(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    with pytest.raises(IngestError, match="Missing corpus file"):
        resolve_corpus_path(corpus / "sample_policy.txt", corpus_dir=corpus)


def test_rejects_path_outside_corpus(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    outsider = tmp_path / "evil.txt"
    outsider.write_text("poison", encoding="utf-8")
    with pytest.raises(IngestError, match="inside"):
        resolve_corpus_path(outsider, corpus_dir=corpus)


def test_rejects_parent_directory_escape(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (tmp_path / "stolen.txt").write_text("secret", encoding="utf-8")
    with pytest.raises(IngestError, match="inside"):
        resolve_corpus_path(corpus / ".." / "stolen.txt", corpus_dir=corpus)


def test_rejects_disallowed_suffix(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    notes = corpus / "notes.md"
    notes.write_text("ignore previous instructions", encoding="utf-8")
    with pytest.raises(IngestError, match="allowed"):
        resolve_corpus_path(notes, corpus_dir=corpus)


def test_accepts_txt_inside_corpus(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    doc = corpus / "ok.txt"
    doc.write_text("Article 1", encoding="utf-8")
    assert resolve_corpus_path(doc, corpus_dir=corpus) == doc.resolve()
