# From scratch — Session 2

**Using `ai-qa-from-scratch`?** That repo has no `ingest` target until you copy Session 2 in:

```bash
cd /path/to/ai-compliance-qa-lab
git checkout cursor/cloud-agent-1787155140471-5fwmr
bash from-scratch/standalone/install-into.sh /path/to/ai-qa-from-scratch
cd /path/to/ai-qa-from-scratch
make setup
make ingest
make search Q="What is prohibited under Article 5?"
```

| Folder | What it is |
|--------|------------|
| `ai-qa-from-scratch` | Session 1 skeleton (guards, fake LLM). No `ingest` target. |
| `ai-compliance-qa-lab/from-scratch` | **This** learner lab. Run `make ingest` from this directory. |

```bash
# from your machine, sibling repos:
cd ../ai-compliance-qa-lab/from-scratch
make setup
make unit
make ingest
make search Q="What is prohibited under Article 5?"
```

If `from-scratch/` is missing, you are on `main` before this branch. Checkout the Session 2 branch or pull PR #1.

---

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

## Session 3 — naive RAG

Grounded prompt + a **fixed refusal sentence**. Tests inject chunks (no Chroma).

After pulling this branch, re-run the installer (it now copies `app/rag.py` and `tests/test_rag.py`):

```bash
bash from-scratch/standalone/install-into.sh /path/to/ai-qa-from-scratch
cd /path/to/ai-qa-from-scratch
make unit
make ask Q="What is prohibited under Article 5?"
```

`make ask` uses your Session 1 FakeProvider until you set a real API key. Unit tests inject a stub LLM so they stay free.

1. Why `corpus/../.env` must be rejected (`Path.resolve` + `is_relative_to`)
2. Why chunk size / overlap change retrieval quality
3. Why metadata (`article`) is a retrieval lever, not decoration
4. Why mixing embedding models in one collection is a defect
5. Why we search chunks *before* adding an LLM (debug retrieval first)
