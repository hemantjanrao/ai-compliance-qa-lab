"""CLI: python scripts/ask.py "What is prohibited?" """
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingest import IngestError
from app.rag import answer


def main() -> int:
    question = " ".join(sys.argv[1:]).strip() or "What is prohibited under Article 5?"
    try:
        result = answer(question)
    except (IngestError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(result.answer)
    print(f"\n(provider={result.provider} model={result.model} chunks={len(result.chunks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
