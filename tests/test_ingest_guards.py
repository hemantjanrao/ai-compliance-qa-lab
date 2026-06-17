"""Ingest guards — OWASP LLM04 (training/ingest data poisoning at source)."""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_ingest_module():
    path = Path("scripts/ingest_corpus.py")
    spec = importlib.util.spec_from_file_location("ingest_corpus", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_ingest_fails_when_corpus_pdf_missing(tmp_path, monkeypatch):
    mod = _load_ingest_module()
    monkeypatch.setattr(mod, "PDF_PATH", tmp_path / "missing.pdf")
    assert mod.main() == 1
