# 03 — The Retrieval Pipeline

Files: `app/retrieval/{config,types,bm25_index,fusion,query_expansion,reranker,pipeline}.py`, `tests/test_retrieval.py`

This is the most technically interesting module in the repo and the one that most differentiates a senior candidate. "We do RAG" is table stakes. "We do multi-query hybrid retrieval with reciprocal rank fusion and cross-encoder reranking, and here's how we measured that it helps" is not.

---

## 1. The funnel

`retrieve_advanced(question, k=5)` with `RAG_CANDIDATE_MULTIPLIER=4`:

```
question
  │
  ├─ expand_queries()          → 1–3 query variants
  ├─ extract_article_filter()  → optional {"article": N} metadata filter
  │
  ▼  for each query q:
  ├─ Chroma dense search  (n_results = k*4 = 20)   → ranked id list
  └─ BM25 sparse search   (k = 20)                 → ranked id list
  │
  ▼  2–6 ranked lists
reciprocal_rank_fusion()  → single fused ranking
  │
  ▼  truncate to k*2 = 10 candidates
cross-encoder rerank(question, candidates, k=5)
  │
  ▼  top 5 by relevance score
_chunks_from_ids()  → RetrievedChunk[] with inverted distances
```

**Widen, then narrow.** Cheap recall-oriented retrievers cast a wide net; an expensive precision-oriented model picks the winners. Same shape as a classic search stack (recall → L1 ranker → L2 ranker), and same shape as candidate generation → ranking in recsys.

The numbers: `k=5` final, `k*4=20` per retriever per query, `k*2=10` reranker inputs. With 2 queries and BM25 available that's up to 4 ranked lists × 20 = 80 candidate slots, deduped by fusion into 10, reranked into 5.

---

## 2. Sparse retrieval — BM25

`app/retrieval/bm25_index.py`

### The algorithm

BM25 scores a document *D* against query *Q*:

$$\text{score}(D,Q)=\sum_{q\in Q}\text{IDF}(q)\cdot\frac{f(q,D)\cdot(k_1+1)}{f(q,D)+k_1\cdot\left(1-b+b\cdot\frac{|D|}{\text{avgdl}}\right)}$$

Three ideas, each of which you should be able to explain plainly:

1. **IDF** — a term appearing in every document carries no information. "the" scores ~0; "biometric" scores high.
2. **Term-frequency saturation** (`k₁`, default 1.5) — the 10th occurrence of a word adds much less than the 2nd. Without saturation, keyword stuffing wins.
3. **Length normalization** (`b`, default 0.75) — a 5,000-word document naturally contains more term occurrences; normalize by length relative to the corpus average so long documents don't dominate.

`rank_bm25`'s `BM25Okapi` implements this. The repo doesn't tune `k₁`/`b` — worth noting as a knob you know exists.

### Tokenization is the whole preprocessing story

```python
_TOKEN_RE = re.compile(r"\w+")

def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())
```

Lowercase + word characters. Deliberately minimal. What's *absent*:

- **No stemming** → "prohibits" and "prohibited" are different terms. Query expansion partially compensates.
- **No stopword removal** → IDF handles it (stopwords get near-zero weight), so this is fine and arguably better than a hardcoded list.
- **`\w+` splits hyphens** → "high-risk" becomes `["high", "risk"]`. Actually helpful here, since the corpus and queries are inconsistent about the hyphen.
- **`\w+` keeps digits** → "Article 5" tokenizes to `["article", "5"]`, so numeric article references are searchable. **This is the main reason BM25 earns its place in this pipeline** — dense embeddings are notoriously bad at exact numbers, and "what does Article 6 say" is the highest-frequency query shape in this domain.

> **Interview line:** "Dense retrieval fails on exact identifiers. Ask a vector store for 'Article 6' and you'll get Articles 5, 7, and 9, because they're semantically adjacent. BM25 gets it right. That's why we run both."

### Persistence

```python
def save(self, path: Path) -> None:
    payload = {"ids": [...], "documents": [...], "metadatas": [...]}
    path.write_text(json.dumps(payload))

@classmethod
def load(cls, path: Path) -> BM25Index | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return cls.from_records(...)
```

It persists the **corpus**, not the fitted index — `BM25Okapi` is rebuilt in `__init__` on load. That's a deliberate simplicity/startup-cost trade: JSON is inspectable and version-independent, at the cost of retokenizing every chunk at load. Fine at this corpus size (~hundreds of chunks); a real system would use a proper inverted index (Elasticsearch/OpenSearch, or Lucene directly).

`load()` returning `Optional` rather than raising is what lets the whole pipeline degrade to dense-only when the index is absent:

```python
bm25 = BM25Index.load(bm25_index_path())   # may be None
...
if bm25 is not None:
    bm25_hits = bm25.search(q, candidate_k)
```

**Graceful degradation as a design default.** A missing sparse index makes results worse, not broken.

### The performance smell

```python
def search(self, query: str, k: int) -> list[tuple[str, float]]:
    scores = self._bm25.get_scores(tokenize(query))
    ranked = sorted(
        ((self.chunks[i].chunk_id, float(scores[i])) for i in range(len(self.chunks))),
        key=lambda item: item[1], reverse=True,
    )
    return ranked[:k]
```

Full sort of *all* N chunks to take the top k. That's O(N log N) where `heapq.nlargest(k, ...)` gives O(N log k). Irrelevant at N=500, meaningful at N=500,000. Notice it, name it, know the fix. Also note `self._by_id` — an O(1) lookup dict built in `__init__`, which is the *right* instinct applied elsewhere in the same class.

---

## 3. Query expansion

`app/retrieval/query_expansion.py`

```python
def expand_queries(question: str) -> list[str]:
    queries = [question.strip()]
    seen = {q.lower() for q in queries}

    match = _ARTICLE_RE.search(question)
    if match:
        article_q = f"Article {match.group(1)}"
        ...append if unseen...

    lowered = question.lower()
    if "prohibit" in lowered and "article 5" not in lowered:
        ...append "Article 5 prohibited AI practices"...
    if "high-risk" in lowered or "high risk" in lowered:
        ...append "high-risk AI systems requirements Annex III"...
    return queries
```

### The design decision

The docstring says it: *"no extra LLM calls."* The textbook multi-query approach asks an LLM to generate paraphrases. That costs a round trip (latency + tokens) on **every** query and introduces non-determinism into retrieval — which makes your eval suite noisier.

This version uses **domain rules**. Deterministic, free, instant, testable:

```python
def test_expand_queries_adds_article_variant():
    queries = expand_queries("What does Article 6 say about high-risk systems?")
    assert any("Article 6" in q for q in queries)
```

You cannot write that test against an LLM-generated expansion.

### What each rule buys

| Rule | Effect |
|---|---|
| Bare "Article N" variant | A short, high-signal query that BM25 nails. Strips distracting context from the user's phrasing. |
| "prohibit" → Article 5 | Maps user vocabulary to legal structure. Users say "banned"/"prohibited"; the regulation puts it all in Article 5. |
| "high-risk" → Annex III | Same idea: the classification criteria live in Article 6 and Annex III, which users don't know to ask for. |

This is a **hand-built query-to-concept mapping** — cheap, explainable, and the honest starting point before reaching for an LLM. The limitation is obvious and you should state it: it doesn't generalize. Every new domain vocabulary gap needs a new `if`. The scaling answer is a synonym/concept table loaded from config, or a small fine-tuned expansion model, both evaluated against `context_recall`.

### The dedup bug worth spotting

```python
    if "prohibit" in lowered and "article 5" not in lowered:
        extra = "Article 5 prohibited AI practices"
        if extra.lower() not in seen:
            queries.append(extra)          # ← `seen` is never updated here
```

The last two branches check `seen` but don't add to it. Harmless today (they append different strings), latent if a third rule is added. Good "find the bug" exercise, and a nice illustration of why `seen`/`queries` should be one helper: `def _add(q): ...`.

### The metadata filter

```python
def extract_article_filter(question: str) -> int | None:
    match = _ARTICLE_RE.search(question)
    if not match:
        return None
    num = int(match.group(1))
    return num if 1 <= num <= 113 else None
```

Returns `None` for "Article 999" — so a fabricated article number becomes an unfiltered semantic search rather than an empty result set. Combined with the system prompt's refusal rule, the model then says it can't find it. That's the mechanism behind `eval/test_adversarial.py::test_refuses_to_fabricate`.

Tested directly:

```python
assert extract_article_filter("Look up Article 42") == 42
assert extract_article_filter("What is prohibited?") is None
assert extract_article_filter("Article 999") is None
```

---

## 4. Reciprocal Rank Fusion

`app/retrieval/fusion.py` — 15 lines that carry a lot of weight.

```python
def reciprocal_rank_fusion(ranked_ids: list[list[str]], *, rrf_k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in ranked_ids:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank + 1)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
```

### The problem it solves

You have a BM25 ranking with scores like `[8.2, 6.1, 5.9]` and a dense ranking with distances like `[0.21, 0.28, 0.33]`. **These scores are not comparable.** Different scales, different directions (higher-better vs lower-better), different distributions per query. Normalizing them (min-max, z-score) requires assumptions that break constantly — a query where BM25 finds nothing produces a degenerate normalization.

RRF's answer: **throw the scores away, keep only the ranks.**

$$\text{RRF}(d)=\sum_{r \in \text{rankers}} \frac{1}{k + \text{rank}_r(d)}$$

Scale-free, distribution-free, hyperparameter-light. From Cormack, Clarke & Buettcher (SIGIR 2009), where it beat learned rank-fusion methods.

### Why `k = 60`

The constant flattens the head of the curve. With `k=60`:

| rank | contribution |
|---|---|
| 0 | 1/61 = 0.01639 |
| 1 | 1/62 = 0.01613 |
| 2 | 1/63 = 0.01587 |
| 9 | 1/70 = 0.01429 |

Rank 0 is only 15% better than rank 9. Compare `k=0`: rank 0 scores 1.0, rank 9 scores 0.1 — a 10× gap.

**The consequence:** with a large `k`, *appearing in multiple rankings* matters more than *being #1 in one ranking*. A chunk at rank 3 in both retrievers (1/64 + 1/64 = 0.03125) beats a chunk at rank 0 in one and absent from the other (1/61 = 0.01639) — by nearly 2×. That's consensus-weighting, and it's exactly the behavior you want from an ensemble.

`k=60` is the value from the original paper, empirically robust across TREC collections. It's a legitimate tuning knob — and a great thing to say you'd tune with `context_recall` as the objective.

### The test encodes exactly this property

```python
def test_reciprocal_rank_fusion_prefers_consensus():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]])
    ids = [cid for cid, _ in fused]
    assert ids[0] in ("a", "b")
    assert "b" in ids[:2]
```

`a`: 1/61 + 1/62 = 0.03252. `b`: 1/62 + 1/61 = 0.03252. Tied — hence `ids[0] in ("a", "b")` rather than a hard assertion. `c` and `d` each appear once (0.01587, 0.01587). The test asserts the *property* (consensus items rank above single-list items) rather than an exact order. **This is property-based assertion discipline, and it's the same instinct you need for testing LLM outputs.**

### Note the `*` in the signature

```python
def reciprocal_rank_fusion(ranked_ids, *, rrf_k: int = 60):
```

`rrf_k` is keyword-only. You cannot call `reciprocal_rank_fusion(lists, 60)`. This prevents a positional-argument mix-up and means `rrf_k` can be reordered or removed without breaking callers. Used consistently across this codebase (`BM25Index.from_records`, `retrieve_chunks`, `answer_with_chunks`, `load_cached_agent_run`).

---

## 5. Cross-encoder reranking

`app/retrieval/reranker.py`

### Bi-encoder vs cross-encoder — the core distinction

| | Bi-encoder (retrieval) | Cross-encoder (reranking) |
|---|---|---|
| Input | query and doc **separately** | query and doc **together**, one sequence |
| Output | two vectors → similarity | a single relevance score |
| Precompute | documents embedded once at ingest | nothing — every pair needs a forward pass |
| Cost per query | 1 embedding + ANN search | N forward passes (N = candidates) |
| Accuracy | good | notably better |

The cross-encoder sees `[CLS] query [SEP] document [SEP]` and applies full attention across both. It can model term interaction — "does *this* document answer *this* query" — which a bi-encoder structurally cannot, because it never sees them together.

The cost is that you can't precompute anything, so it's O(candidates) model calls. **That's why it goes last, on 10 candidates, not first on 500 chunks.**

`cross-encoder/ms-marco-MiniLM-L-6-v2` is trained on MS MARCO passage ranking — the standard cheap reranker. 6 layers, ~22M params, CPU-viable.

### The caching pattern

```python
_reranker = None      # ← vestigial, unused

@lru_cache(maxsize=1)
def _get_cross_encoder():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(rerank_model_name())
```

Two techniques:

**`@lru_cache(maxsize=1)` as a lazy singleton.** The model loads once per process. `maxsize=1` because the function takes no arguments — there's only one cache entry ever. This is idiomatic and thread-safe for the load itself.

**The import is *inside* the function.** `sentence_transformers` pulls in torch and transformers — several seconds and hundreds of MB. Importing at module scope would make `import app.retrieval.pipeline` slow, which would make `make unit` slow, which would make `tests/test_retrieval.py` (which imports from this package) slow. Deferring the import means the cost is paid only when reranking actually runs. **This is a real, load-bearing pattern in ML codebases.**

(`_reranker = None` at module level is dead code left over from an earlier manual-memoization approach. Deleting it is a legitimate small PR.)

### The early returns

```python
if not candidates:
    return []
if len(candidates) == 1:
    return [(candidates[0][0], 1.0)]
```

Zero candidates: nothing to rank. One candidate: it wins by definition — skip the model load entirely. That second branch is why unit tests that exercise a single-chunk path don't trigger a torch import.

The synthetic score `1.0` is a small lie (cross-encoder scores aren't bounded to [0,1] — `ms-marco` outputs raw logits, often negative) but it's only used for ordering, and there's nothing to order.

### Sorting

```python
ranked = sorted(
    zip((cid for cid, _ in candidates), scores),
    key=lambda item: float(item[1]),
    reverse=True,
)
```

`float(item[1])` because `model.predict` returns a `numpy.float32` array; the explicit cast avoids numpy comparison semantics in the sort key. Minor, but the kind of detail that bites in aggregation later.

---

## 6. Orchestration

`app/retrieval/pipeline.py::retrieve_advanced`

### Metadata filter with fallback

```python
where = {"article": article} if article is not None else None
try:
    res = coll.query(query_texts=[q], n_results=candidate_k, where=where)
except Exception:
    res = coll.query(query_texts=[q], n_results=candidate_k)
```

If the filtered query fails — bad filter syntax, no chunks carry that metadata key, Chroma version difference — fall back to unfiltered. **Degrade, don't fail.**

The tradeoff, and you should name it: a bare `except Exception` also swallows genuine bugs. A malformed `where` clause would silently produce unfiltered results forever, and retrieval quality would quietly be worse than you think. A better version logs the exception or narrows to Chroma's specific filter error type. Worth proposing as a fix.

Also note: with a filter active, an article whose chunks all failed the 1–113 metadata tagging returns nothing from dense search — but BM25 (unfiltered) still contributes. The hybrid design absorbs the failure.

### Building the reranker's input

```python
candidate_ids = [cid for cid, _ in fused]
candidate_texts: list[tuple[str, str]] = []
if bm25 is not None:
    for cid in candidate_ids:
        chunk = bm25.get(cid)
        if chunk:
            candidate_texts.append((cid, chunk.text))
else:
    fetched = coll.get(ids=candidate_ids, include=["documents"])
    ...
```

Text comes from BM25's in-memory store when available (O(1) dict lookup, no I/O) and from Chroma otherwise (one batched `get`, not N single gets). Both paths are batched or free. Nice.

### The reranker safety net

```python
reranked = rerank(question, candidate_texts, k=k)
if not reranked:
    reranked = fused[:k]
```

If reranking yields nothing, fall back to the fused order. Again: degrade to a worse-but-working result.

Note `rerank(question, ...)` uses the **original** question, not the expanded variants. Correct — the reranker's job is "does this chunk answer what the user actually asked", and expansion queries are retrieval aids, not the user's intent.

### The score inversion — read this twice

```python
score = score_by_id[cid]
distance = 1.0 / (1.0 + score) if score > 0 else 1.0
```

`RetrievedChunk.distance` is defined as lower-is-better (it's a *distance*), because `retrieve_basic` fills it with Chroma's actual L2 distance. But fusion and reranking produce higher-is-better *scores*. The inversion `1/(1+s)` maps them into the same direction so the two retrieval modes return structurally identical objects.

This is an **API compatibility shim**, and it has real consequences:

- The mapping is monotone-decreasing, so **ordering is preserved** — which is all that actually matters downstream.
- The magnitudes are **not** comparable to `retrieve_basic`'s L2 distances. A "distance" of 0.5 means something different in each mode.
- Negative cross-encoder scores (common with `ms-marco` logits) hit the `else 1.0` branch and all collapse to the same value, losing their relative ordering *within the returned objects* — though the list order is already correct, so nothing breaks.

The honest design would be a `score: float` field plus a `score_kind: Literal["distance","relevance"]`, or just documenting that `distance` is an opaque ordering key. **This is exactly the kind of nuance interviewers probe for: "your two code paths return the same type — is the value actually the same thing?"**

### The strategy switch

```python
def retrieve_chunks(question, k=5, *, mode: RetrievalMode | None = None):
    mode = mode or get_retrieval_mode()
    if mode == RetrievalMode.BASIC:
        return retrieve_basic(question, k)
    return retrieve_advanced(question, k)
```

`mode=None` → read env. Explicit mode → override. This single seam gives you:

- `RAG_RETRIEVAL_MODE` for deployment-level config
- a Streamlit dropdown for live comparison
- a `retrieval_mode` field on the API request for per-request A/B
- `RAGResult.retrieval_mode` recorded on every result, so eval reports can attribute scores to a strategy

**That last point is the important one.** You can run the full RAGAS suite in both modes and produce a defensible number for what hybrid+rerank is worth. "We built advanced retrieval and it improved context_precision from X to Y" is a materially stronger claim than "we built advanced retrieval."

---

## Exercises

1. Compute RRF by hand for `[["a","b","c"], ["b","a","d"]]` with `k=60` and with `k=1`. Explain how the winner changes and why.
2. Add printf instrumentation to `retrieve_advanced` reporting candidate counts at each funnel stage. Run 5 questions. Are the numbers what you predicted?
3. Set `RAG_CANDIDATE_MULTIPLIER=1`, then `=10`. Measure latency and (with keys) RAGAS `context_precision`. Where's the knee?
4. Replace the `sorted()` in `BM25Index.search` with `heapq.nlargest`. Benchmark at N=500 and at N=50,000 (synthesize chunks).
5. Fix the `seen` dedup gap in `expand_queries` and add a regression test.
6. Add a `score` field to `RetrievedChunk` alongside `distance`, populate both correctly per mode, and update consumers. What breaks?
7. Make the reranker optional via env var, run RAGAS both ways, and write the one-paragraph result.

## Interview questions this section answers

- "Walk me through your retrieval pipeline." *(draw the funnel)*
- "Why hybrid search? Isn't a good embedding model enough?" *(exact identifiers, out-of-vocabulary terms, the Article-6 example)*
- "How do you combine rankings with incomparable scores?" *(RRF, and why not min-max normalization)*
- "What's a cross-encoder and why don't you use it for the whole corpus?"
- "How would you prove the advanced pipeline is better than the basic one?"
- "What happens when a component of your retrieval stack is unavailable?"
