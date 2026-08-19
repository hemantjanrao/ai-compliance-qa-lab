# From scratch — Session 2

Learner track **inside this repo**. Production RAG still lives in `app/` and
`scripts/ingest_corpus.py`. Do not copy those files here.

Session 2 pipeline:

```
allowlisted file in corpus/
        → split into overlapping chunks + article metadata
        → embed with local MiniLM (no API key)
        → store in Chroma
        → search chunks (still no LLM — that is Session 3)
```

## Fast tests (no model download)

From this folder:

```bash
make setup
make unit
```

Or from the repo root:

```bash
make learn-s2
```

## Optional: actually ingest and search

Needs extra packages (`chromadb`, `sentence-transformers`) and downloads MiniLM once (~80MB):

```bash
cd from-scratch
make ingest
make search Q="What is prohibited under Article 5?"
```

## What you should be able to explain

1. Why `corpus/../.env` must be rejected (`Path.resolve` + `is_relative_to`)
2. Why chunk size / overlap change retrieval quality
3. Why metadata (`article`) is a retrieval lever, not decoration
4. Why mixing embedding models in one collection is a defect
5. Why we search chunks *before* adding an LLM (debug retrieval first)
