"""CLI: python scripts/search_chunks.py "What is prohibited?" """
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scratch.ingest import IngestError
from scratch.pipeline import search_chunks


def main() -> int:
    question = " ".join(sys.argv[1:]).strip() or "What is prohibited under Article 5?"
    try:
        hits = search_chunks(question, k=3)
    except (IngestError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"Query: {question}\n")
    for i, hit in enumerate(hits, start=1):
        meta = hit["metadata"] or {}
        print(
            f"--- hit {i}  id={hit['id']}  page={meta.get('page')}  "
            f"article={meta.get('article')}  distance={hit['distance']}"
        )
        print(hit["text"][:500])
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
