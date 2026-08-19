# 02 — Ingestion and Embeddings

Files: `scripts/ingest_corpus.py`, `app/embeddings.py`, `tests/test_ingest_guards.py`

This is the layer everyone under-invests in and then blames the LLM for. Retrieval quality is capped by chunking quality.

---

## 1. The ingest pipeline, end to end

```
corpus/eu_ai_act.pdf
   │  PyPDFLoader.load()
   ▼
Document[]  (one per page, with metadata={"page": n, "source": ...})
   │  RecursiveCharacterTextSplitter.split_documents()
   ▼
Chunk[]  (~2000 chars, 100 overlap, split on structural boundaries)
   │  _chunk_metadata()          → adds {"source": "page_N", "page": N, "article": M?}
   ├──────────────────────────────────────────────┐
   ▼                                              ▼
ChromaDB collection "eu_ai_act"              BM25Index
(dense vectors via embedding fn)             (chroma_db/bm25_index.json)
```

Two indexes are built from the **same** id/document/metadata triple. That symmetry is what makes hybrid retrieval work — a chunk id means the same thing in both systems, so ranked lists can be fused.

---

## 2. Loading

```python
docs = PyPDFLoader(str(PDF_PATH)).load()
```

`PyPDFLoader` wraps `pypdf`. One `Document` per page, `page_content` is extracted text, `metadata` carries `page`.

**What this loses, and why it matters for QA:**

- Table structure (the AI Act's Annexes are tabular) — flattened to whitespace-separated runs
- Column order on multi-column layouts can interleave
- Footnotes merge into body text
- Headers/footers repeat on every page, adding noise to every chunk

None of these are fixed here. That's a legitimate scope decision for a lab, but you should be able to say what you'd do instead: layout-aware extraction (`unstructured`, `pymupdf` with block coordinates), or a document-AI service, then evaluate whether retrieval metrics actually improve. **Never adopt a heavier parser without measuring — that's what the RAGAS suite is for.**

---

## 3. Chunking — the highest-leverage knob

```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=2000,
    chunk_overlap=100,
    separators=["\nArticle ", "\nChapter ", "\n\n", "\n", ". ", " "],
)
```

### How `RecursiveCharacterTextSplitter` actually works

It tries the separators **in order**. For each separator it splits the text; if a resulting piece is still longer than `chunk_size`, it recurses into that piece with the *next* separator. If it runs out of separators, it hard-splits at `chunk_size`.

So the effect of putting `"\nArticle "` first is: **prefer to break at article boundaries; only break mid-article if an article exceeds 2000 chars.** That's structure-aware chunking without writing a parser.

### The separator list is domain knowledge encoded as config

Generic RAG tutorials use `["\n\n", "\n", " ", ""]`. This repo's list starts with two legal-document separators. That single change is the difference between chunks that begin "…and shall be deemed compliant. Article 6 Classification rules…" and chunks that begin cleanly at "Article 6".

Why it matters downstream: `_chunk_metadata` uses a regex to find the *first* article mention in a chunk. If chunks straddle boundaries, that regex tags the chunk with the wrong article, and the `where={"article": n}` filter in `retrieve_advanced` returns wrong results. **Chunking bugs surface three layers away.**

### Size and overlap tradeoffs

| Knob | Too small | Too large |
|---|---|---|
| `chunk_size` | Answer spans multiple chunks; retrieval must get *all* of them right; context_recall drops | Chunk contains the answer *plus* three unrelated topics; embedding is a blurry average; precision drops; more tokens per query |
| `chunk_overlap` | An answer straddling a boundary appears fully in no chunk | Duplicate content inflates the index, wastes retrieval slots on near-identical chunks |

2000/100 (5% overlap) is on the large-chunk end. Rationale for a legal corpus: articles are self-contained units and you want the whole obligation, not half of it. The cost is precision — which is exactly why the pipeline adds a cross-encoder reranker downstream (see [`03`](03_RETRIEVAL_PIPELINE.md)).

**Exercise you should actually run:** re-ingest at 500, 1000, 2000, 4000 and record chunk count + RAGAS `context_precision`/`context_recall` for each. This is the single most instructive experiment in the repo, and "we measured chunk size against context precision" is a strong interview line.

---

## 4. Metadata enrichment

```python
_ARTICLE_RE = re.compile(r"\bArticle\s+(\d{1,3})\b")

def _chunk_metadata(page_content: str, page: int) -> dict:
    meta: dict = {"source": f"page_{page}", "page": page}
    match = _ARTICLE_RE.search(page_content)
    if match:
        article = int(match.group(1))
        if 1 <= article <= 113:
            meta["article"] = article
    return meta
```

### What's good here

- **Compiled once at module level.** `re.compile` outside the function; the regex is reused across thousands of chunks.
- **`\b` word boundaries** prevent matching "Subarticle" or "Article" inside a longer token.
- **`\s+`** tolerates "Article  6" and "Article\n6".
- **Range validation (1–113).** The EU AI Act has 113 articles. A match on "Article 999" is rejected rather than stored as garbage. The same bound appears in `app/agent/tools.py::lookup_article` and in `app/retrieval/query_expansion.py::extract_article_filter`.

### What's weak, and you should say so

- **`.search()` takes the first match only.** A chunk mentioning "Article 6 … see also Article 9" is tagged `article=6`. Cross-references pollute the tag.
- **The 113 bound is duplicated in three files** as a magic number. It belongs in one constant. Good refactor exercise.
- **Source is `page_N`, not a citation.** Fine for a lab; a production compliance tool would want article + paragraph so answers are legally citable.

> **Interview framing:** "Metadata is a retrieval lever, not decoration. Ours enables an article-scoped filter that turns a fuzzy semantic search into a near-exact lookup for the most common query shape in the domain."

---

## 5. Idempotent ingest

```python
try:
    client.delete_collection(name)
except Exception:
    pass
coll = client.create_collection(name=name, embedding_function=embed_fn)
```

Delete-then-create rather than upsert. Consequences:

- ✅ Re-running ingest after changing chunk size gives a clean index — no orphaned chunks from the old configuration. Since ids are positional (`chunk_0`, `chunk_1`, …), an upsert would leave stale chunks whenever the new run produces fewer chunks.
- ❌ Not safe to run against a live serving index. There's a window with no data.
- ❌ The bare `except Exception: pass` also swallows permission errors and connection failures, so a genuinely broken Chroma looks like a fresh one.

For a lab this is right. At scale you'd build into a new collection name and swap an alias atomically (blue/green indexing). Be ready to say that.

### Positional ids are a real coupling

```python
ids = [f"chunk_{i}" for i in range(len(chunks))]
```

`chunk_47` means "the 48th chunk produced by *this* configuration". Change chunk size and `chunk_47` is different text. Anything that persisted a chunk id — the BM25 index, the `.eval_cache`, a bug report — is silently invalidated. A content hash (`sha256(text)[:16]`) would make ids stable and make re-ingest genuinely incremental.

---

## 6. Embeddings

`app/embeddings.py`:

```python
def get_chroma_embedding_function() -> EmbeddingFunction[Documents]:
    if get_embedding_provider() == "openai":
        return OpenAIEmbeddingFunction(
            api_key=os.environ["OPENAI_API_KEY"],
            model_name=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        )
    return SentenceTransformerEmbeddingFunction(
        model_name=os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        device=os.getenv("EMBEDDING_DEVICE", "cpu"),
        normalize_embeddings=True,
    )
```

### The two options

| | `all-MiniLM-L6-v2` (local) | `text-embedding-3-small` (OpenAI) |
|---|---|---|
| Dimensions | 384 | 1536 |
| Cost | $0 | ~$0.02 / 1M tokens |
| Latency | local CPU, ~ms | network round trip |
| Max sequence | 256 word pieces (⚠️) | 8191 tokens |
| Quality on legal text | decent | better |
| CI-friendly | yes — no secret needed | needs a key |

The CI workflow sets `EMBEDDING_PROVIDER: local` precisely so `eval-fast` can ingest and run without an OpenAI key.

### ⚠️ The truncation trap

`all-MiniLM-L6-v2` has a **256 token** maximum sequence length. Chunks are **2000 characters** ≈ 400–500 tokens. **Roughly half of each chunk is silently truncated before embedding.**

This is not a bug the repo announces, and it is exactly the kind of thing a strong candidate notices. Implications:

- The dense vector represents only the chunk's opening. Content in the back half is unreachable by semantic search.
- BM25 (which indexes the full text) partially compensates — another argument for hybrid.
- The cross-encoder reranker *also* has a length limit (512 for `ms-marco-MiniLM-L-6-v2`), so it sees more but still not all.

**Verify it yourself:** embed a chunk, then embed only its first 200 words, and compare cosine similarity. If it's ~1.0, you've confirmed truncation.

**Fixes, in order of effort:** reduce `chunk_size` to ~1000; switch to a longer-context local model (`bge-base-en-v1.5`, 512 tokens; `nomic-embed-text`, 8192); or use OpenAI embeddings. Then measure whether RAGAS moves — that's the whole point of having the harness.

### `normalize_embeddings=True`

L2-normalizes each vector to unit length. Then dot product ≡ cosine similarity, and Chroma's default L2 distance becomes a monotone function of cosine distance. Without normalization, vector *magnitude* (which correlates with text length, not meaning) leaks into the ranking.

`eval/ragas_config.py` mirrors this with `encode_kwargs={"normalize_embeddings": True}` — the RAGAS judge's embeddings must match the app's, or `answer_similarity` scores aren't comparable to anything.

### Bi-encoder mental model

A bi-encoder embeds query and document **independently**, then compares vectors. That's what makes it fast (documents are embedded once at ingest, queries once at search) and what makes it approximate (the model never sees query and document together). Hold that thought — it's the entire justification for the cross-encoder reranker in [`03`](03_RETRIEVAL_PIPELINE.md).

### `embed_text` for eval

```python
def embed_text(text: str) -> np.ndarray:
    fn = get_chroma_embedding_function()
    vectors: Embeddings = fn([text])
    return np.array(vectors[0])
```

Used by `eval/helpers.py::embed`, which feeds `test_metamorphic.py` and `test_bias.py`. Note it constructs the embedding function on **every call** — for `SentenceTransformerEmbeddingFunction` that may reload the model. In a loop over paraphrase groups this is measurable overhead. An `@lru_cache` on `get_chroma_embedding_function` would fix it (the reranker already uses exactly that pattern — see `app/retrieval/reranker.py`). Good, small, real optimization exercise.

---

## 7. Ingest as a tested contract

`tests/test_ingest_guards.py` is short but conceptually dense:

```python
def _load_ingest_module():
    path = Path("scripts/ingest_corpus.py")
    spec = importlib.util.spec_from_file_location("ingest_corpus", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_ingest_fails_when_corpus_pdf_missing(tmp_path, monkeypatch):
    mod = _load_ingest_module()
    monkeypatch.setattr(mod, "PDF_PATH", tmp_path / "missing.pdf")
    assert mod.main() == 1
```

**Why the import gymnastics?** `scripts/` isn't a package (not in `[tool.setuptools.packages.find] include`), so `import scripts.ingest_corpus` fails. `importlib.util.spec_from_file_location` loads a module from an arbitrary path. This is the same machinery `import` uses internally — worth understanding, covered in [`11_ADVANCED_PYTHON.md`](11_ADVANCED_PYTHON.md) §10.

**Why `monkeypatch.setattr(mod, "PDF_PATH", ...)`?** `PDF_PATH` is a module-level constant computed at import. Patching the *attribute on the loaded module object* is the only way to redirect it. `monkeypatch` restores it after the test.

**Why does this count as security (LLM04)?** The corpus is the ground truth for every answer. If ingestion silently succeeds on a missing or substituted file, the app serves confident answers grounded in nothing. Returning exit code `1` makes the failure loud and makes `make ingest` fail in a shell pipeline. The test pins that behavior.

**What's missing** — say this out loud in an interview: there's no integrity check on the PDF itself. A checksum assertion against the published EU document would close the loop on "is this the corpus we think it is". That's a two-line addition and a strong thing to propose.

---

## Exercises

1. Re-ingest at `chunk_size` ∈ {500, 1000, 2000, 4000}. Record chunk count and, if you have keys, RAGAS `context_precision` / `context_recall`. Write a one-paragraph conclusion.
2. Prove or disprove the MiniLM truncation issue empirically (cosine of full chunk vs first 200 words).
3. Change chunk ids to content hashes. What else must change? (BM25 index, `.eval_cache` keys — trace it.)
4. Add a SHA-256 checksum check for `corpus/eu_ai_act.pdf` and a test for it.
5. Make `_chunk_metadata` capture *all* article mentions as a list. Does Chroma's `where` filter support list membership? Design around the answer.
6. Add `@lru_cache` to `get_chroma_embedding_function` and measure the speedup on `eval/test_metamorphic.py`. What's the risk of caching it? (Hint: env var changes mid-process.)

## Interview questions this section answers

- "How do you choose chunk size?" → *measure it against context precision/recall; here's the experiment*
- "What's the difference between a bi-encoder and a cross-encoder?"
- "How do you handle documents with structure — do you just split on newlines?"
- "What can go wrong in ingestion that you'd only notice at query time?"
- "How do you prevent data poisoning in a RAG system?"
