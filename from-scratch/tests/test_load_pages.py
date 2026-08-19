"""Load the committed sample policy without Chroma."""
from __future__ import annotations

from pathlib import Path

from scratch.ingest import CORPUS_DIR
from scratch.pipeline import load_pages


def test_sample_policy_loads_as_one_page():
    path = CORPUS_DIR / "sample_policy.txt"
    assert path.is_file()
    pages = load_pages(path)
    assert pages[0][0] == 1
    assert "Article 5" in pages[0][1]
