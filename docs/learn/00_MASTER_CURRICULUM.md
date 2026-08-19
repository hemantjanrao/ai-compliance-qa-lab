# Master Curriculum — Every Concept in This Repo + Advanced Python

**Target:** total mastery of `ai-compliance-qa-lab` (~3,880 lines of Python across 56 files) plus the advanced Python it exercises.
**Mode:** full-time, ~7 days, ~8h/day.
**Outcome:** you can rebuild any module from scratch, defend every design decision in an interview, and explain the Python underneath.

---

## How this differs from the existing docs

| Doc | What it gives you |
|---|---|
| `docs/ONBOARDING_7_DAYS.md`, `docs/STUDY_GUIDE.md` | **Activities** — do this, run that |
| `docs/ARCHITECTURE.md`, `docs/EVAL_STRATEGY.md` | **Decisions** — why the system is shaped this way |
| **`docs/learn/` (this set)** | **Concepts + code** — what every line does, the theory behind it, and the interview framing |

Use all three. This set is the reference; onboarding is the schedule.

---

## The concept inventory

Everything this repo teaches, grouped. Each row links to its deep dive.

### Layer 1 — Application foundations → [`01_FOUNDATIONS.md`](01_FOUNDATIONS.md)

| Concept | Where |
|---|---|
| src-less package layout, editable installs, `[project.optional-dependencies]` | `pyproject.toml` |
| Dependency pinning as supply-chain control (LLM03) | `pyproject.toml`, `tests/test_supply_chain.py` |
| Makefile as the single task interface; `.venv` fallback logic | `Makefile` |
| Config-by-environment, fail-fast validation | `app/retrieval/config.py`, `app/embeddings.py` |
| Provider abstraction via ABC — swap Anthropic/OpenAI without touching call sites | `app/providers.py` |
| Retry policy with *selective* retryability (never retry auth/quota) | `app/providers.py` `_is_retryable` |
| Exception → actionable UX message translation | `app/env_check.py` `format_api_error` |
| Input guards — DoS via oversized prompts (LLM05) | `app/guards.py` |
| Pydantic v2 request validation, `field_validator` | `app/main.py` |
| Health endpoint that degrades instead of lying | `app/main.py` `/health` |

### Layer 2 — Ingestion & embeddings → [`02_INGESTION_AND_EMBEDDINGS.md`](02_INGESTION_AND_EMBEDDINGS.md)

| Concept | Where |
|---|---|
| PDF → documents → chunks; `RecursiveCharacterTextSplitter` separator hierarchy | `scripts/ingest_corpus.py` |
| Chunk size / overlap tradeoffs (2000 / 100 here) | same |
| Structure-aware separators (`\nArticle `, `\nChapter `) | same |
| Metadata enrichment as a retrieval lever (article number extraction) | `_chunk_metadata` |
| Idempotent ingest — delete-then-create collection | same |
| Dense embeddings: bi-encoder, normalization, cosine vs L2 | `app/embeddings.py` |
| Local (MiniLM, free) vs hosted (`text-embedding-3-small`) tradeoff | same |
| Ingest failure as a tested contract (LLM04) | `tests/test_ingest_guards.py` |

### Layer 3 — Retrieval pipeline → [`03_RETRIEVAL_PIPELINE.md`](03_RETRIEVAL_PIPELINE.md)

| Concept | Where |
|---|---|
| Sparse retrieval: BM25 scoring, TF saturation, IDF, length norm | `app/retrieval/bm25_index.py` |
| Persisting a sparse index alongside a vector DB | `BM25Index.save/load` |
| Hybrid search — why lexical + semantic beat either alone | `pipeline.retrieve_advanced` |
| Reciprocal Rank Fusion, the `k=60` constant, rank-vs-score fusion | `app/retrieval/fusion.py` |
| Multi-query expansion without extra LLM calls | `app/retrieval/query_expansion.py` |
| Metadata filtering (`where={"article": n}`) with graceful fallback | `pipeline.retrieve_advanced` |
| Cross-encoder re-ranking; bi-encoder vs cross-encoder | `app/retrieval/reranker.py` |
| Candidate multiplier / funnel sizing (k → 4k → 2k → k) | `config.candidate_multiplier` |
| Score→distance inversion for API compatibility | `pipeline._chunks_from_ids` |
| Strategy switch: basic vs advanced as an A/B lever | `config.RetrievalMode` |

### Layer 4 — RAG core & security → [`04_RAG_CORE_AND_SECURITY.md`](04_RAG_CORE_AND_SECURITY.md)

| Concept | Where |
|---|---|
| Grounding prompt design; explicit refusal string as a testable contract | `app/rag.py` `SYSTEM_PROMPT` |
| Context assembly with source attribution | `answer_with_chunks` |
| Seam design — `answer_with_chunks` split out so tests can inject poisoned chunks | `app/rag.py` |
| OWASP LLM01 prompt injection (direct + indirect) | `eval/test_adversarial.py` |
| OWASP LLM08 poisoned retrieval | `tests/test_rag_security.py` |
| Token accounting as a first-class result field | `RAGResult` |
| Prompt-as-artifact: v1 vs v2 regression | `promptfoo/prompt-v*.txt` |

### Layer 5 — The agent → [`05_AGENT.md`](05_AGENT.md)

| Concept | Where |
|---|---|
| ReAct loop mechanics on the Anthropic tool-use API | `app/agent/runner.py` |
| Message-history contract: assistant blocks ↔ `tool_result` blocks by `tool_use_id` | `_run_agent_loop` |
| Stop conditions: `end_turn`, `no_tool_results`, `max_steps` | same |
| Trajectory as the testable artifact (not just the answer) | `TrajectoryStep`, `AgentRun` |
| Tool schema design (JSON Schema, enums, required, descriptions-as-prompt) | `app/agent/tools.py` |
| Tool registry + fail-loud on hallucinated tools | `execute_tool` |
| Errors returned to the model as `is_error` results, not exceptions | `_run_agent_loop` |
| Deterministic tools (fine table, risk heuristic) = unit-testable | `tests/test_tools.py` |
| Step budgets, loop detection, tool flooding | `eval/agent/` |

### Layer 6 — Observability → [`06_OBSERVABILITY.md`](06_OBSERVABILITY.md)

| Concept | Where |
|---|---|
| Traces/spans/observation types; why AI QA needs them | `app/observability.py` |
| Null-object pattern — no-op when keys absent | `trace()` |
| Lazy singleton client, module-level memoized `_enabled` | `get_langfuse` |
| `@contextmanager` + decorator built on the same primitive | `trace` / `observe` |
| Payload truncation and dataclass serialization for trace safety | `_safe` |
| Flush semantics for short-lived processes | `flush()` |

### Layer 7 — Eval harness → [`07_EVAL_HARNESS.md`](07_EVAL_HARNESS.md)

| Concept | Where |
|---|---|
| Separation of **measurement** (tests) from **gating** (`gate.py`) | `eval/reporting.py` |
| Report artifact schema, versioning, git-commit stamping | `ReportCollector` |
| Class-level mutable state; nested dotted-path setters | same |
| pytest hooks: `pytest_configure`, `pytest_collection_modifyitems`, `pytest_sessionfinish` | `eval/conftest.py` |
| Dynamic skipping by provider readiness / `EVAL_PROVIDERS` | same |
| Content-addressed caching of agent runs (SHA-256 key) | `_cache_key`, `load_cached_agent_run` |
| Indirect parametrization (`indirect=True`) | `agent_run_for_case` |
| Golden datasets as contracts (JSONL, tags, `must_refuse`) | `eval/datasets/golden.jsonl` |
| Thresholds as data, not code | `eval/thresholds.yaml` |
| Metric-name registry as single source of truth | `eval/metrics_registry.py` |

### Layer 8 — Metrics & test types → [`08_EVAL_METRICS.md`](08_EVAL_METRICS.md)

| Concept | Where |
|---|---|
| RAGAS: 8 metrics, what each actually measures, NaN handling | `eval/test_ragas.py` |
| Judge LLM ≠ app LLM; explicit judge config | `eval/ragas_config.py` |
| DeepEval built-ins vs G-Eval custom rubrics | `eval/deepeval_helpers.py` |
| Writing a rubric that discriminates (and case filtering per rubric) | `filter_cases_for_geval` |
| Metamorphic testing — paraphrase invariance via embedding cosine | `eval/test_metamorphic.py` |
| Counterfactual fairness / demographic invariance | `eval/test_bias.py` |
| Adversarial suites mapped to OWASP LLM Top 10 | `eval/test_adversarial.py` |
| Latency p95 and cost-per-query budgets as tests | `eval/test_budget.py` |
| Config-driven prompt regression (promptfoo assertions) | `eval/test_promptfoo.py`, `scripts/generate_promptfoo_tests.py` |
| Non-determinism: why assert on distributions/properties, not strings | across |

### Layer 9 — Agent evaluation → [`09_AGENT_EVAL.md`](09_AGENT_EVAL.md)

| Concept | Where |
|---|---|
| Path vs destination: trajectory correctness ≠ answer correctness | `docs/AGENT_QA.md`, `eval/agent/` |
| Expected / forbidden / any-of tool assertions | `test_tool_selection.py` |
| Loop detection via call-signature `Counter` | same |
| Step-budget tests with tolerance | same |
| `ToolCorrectnessMetric`, `TaskCompletionMetric`, G-Eval trajectory judge | `test_deepeval_agent.py` |
| Agent-specific adversarial: tool hallucination, flooding, retry storms | `eval/agent/test_adversarial.py` |

### Layer 10 — Gate & CI → [`10_GATE_AND_CI.md`](10_GATE_AND_CI.md)

| Concept | Where |
|---|---|
| Absolute floors vs relative regression vs latency regression vs adversarial-stickiness | `eval/gate.py` |
| Warnings-vs-failures on missing data (and why that's a real risk) | same |
| Baseline promotion as a deliberate release decision | `--promote` |
| CLI design with `argparse`, exit codes as the CI contract | `main()` |
| Markdown summary artifact for PR review | `format_gate_summary` |
| Cost-tiered CI: unit (free) → eval-fast → eval-full (manual) | `.github/workflows/eval-gate.yml` |
| Caching Chroma + `.eval_cache` in CI | same |
| Testing the gate itself | `tests/test_gate.py` |

### Layer 11 — Advanced Python → [`11_ADVANCED_PYTHON.md`](11_ADVANCED_PYTHON.md)

Everything above, taught as Python: ABCs, dataclasses, decorators & `functools`, context managers, protocols & structural typing, `Literal`/`TypeVar`/`TYPE_CHECKING`, generators, descriptors, `__init_subclass__`, `lru_cache`, `contextlib`, import machinery, pytest internals, packaging, concurrency notes, and the memory/GC model — each anchored to a real file in this repo.

### Layer 12 — Interview drills → [`12_INTERVIEW_DRILLS.md`](12_INTERVIEW_DRILLS.md)

Question bank, whiteboard prompts, STAR stories, self-assessment scorecard.

---

## 7-day full-time schedule

Each day: **Read (2h) → Code (4h) → Break-it (1h) → Explain out loud (1h)**.
The "explain out loud" block is not optional — it is the difference between recognizing and knowing.

### Day 1 — Foundations + ingestion + embeddings
- Read: [`01_FOUNDATIONS.md`](01_FOUNDATIONS.md), [`02_INGESTION_AND_EMBEDDINGS.md`](02_INGESTION_AND_EMBEDDINGS.md)
- Python focus: ABCs, dataclasses, `Literal`, module-level config functions, `functools.wraps`
- Code: `make setup`, `make ingest`, `make unit`. Then re-ingest at `chunk_size=500` and `chunk_size=4000`; record chunk counts and eyeball retrieval quality.
- Break-it: point `EMBEDDING_PROVIDER` at an invalid value; confirm the error is immediate and readable. Delete `chroma_db/` and check `/health` reports `degraded`.
- Explain: "Walk me through what happens between a PDF and a vector store."

### Day 2 — Retrieval pipeline
- Read: [`03_RETRIEVAL_PIPELINE.md`](03_RETRIEVAL_PIPELINE.md)
- Python focus: `@lru_cache`, generator expressions in `sorted`, `zip`, `TYPE_CHECKING`, `Enum(str, Enum)`
- Code: implement RRF from scratch on paper for two ranked lists, then verify against `reciprocal_rank_fusion`. Instrument `retrieve_advanced` to print candidate counts at each funnel stage.
- Break-it: set `RAG_CANDIDATE_MULTIPLIER=1` and compare answers. Disable the reranker (return `fused[:k]`) and compare.
- Explain: "Why hybrid + rerank instead of just a bigger `k`?"

### Day 3 — RAG core, security, agent
- Read: [`04_RAG_CORE_AND_SECURITY.md`](04_RAG_CORE_AND_SECURITY.md), [`05_AGENT.md`](05_AGENT.md)
- Python focus: `unittest.mock` (`patch`, `MagicMock`, `call_args`), exception design, Pydantic v2 validators
- Code: add a 5th agent tool (e.g. `list_annex_iii_categories`) with schema, registry entry, and unit tests. Add golden trajectory cases for it.
- Break-it: weaken rule 4 in `SYSTEM_PROMPT`, run `tests/test_rag_security.py` and `eval/test_adversarial.py`, observe which fail.
- Explain: "How do you test a system whose output is non-deterministic?"

### Day 4 — Observability + eval harness
- Read: [`06_OBSERVABILITY.md`](06_OBSERVABILITY.md), [`07_EVAL_HARNESS.md`](07_EVAL_HARNESS.md)
- Python focus: `@contextmanager`, decorator factories, pytest hooks & fixtures, `hashlib`, indirect parametrization
- Code: stand up Langfuse (`docker compose up -d`), run a few queries, trace one bad answer end-to-end. Then write a new pytest fixture that caches RAG results the way `agent_run_for_case` caches agent runs.
- Break-it: delete `.eval_cache/`, time the agent suite; restore, time again. Quantify the saving.
- Explain: "A user says the answer quality dropped this week. Walk me through your investigation."

### Day 5 — Metrics: RAGAS, DeepEval, metamorphic, bias, adversarial, budget
- Read: [`08_EVAL_METRICS.md`](08_EVAL_METRICS.md)
- Python focus: `numpy` basics, `math.isnan`, parametrize stacking, `pytest.skip`/`fail` semantics
- Code: add 3 golden cases including one `must_refuse: true`. Write one new G-Eval rubric and wire it through `metrics_registry` → `thresholds.yaml` → `gate.py`.
- Break-it: lower `metamorphic.paraphrase_similarity` to 0.95 and see what fails; reason about false-positive rate.
- Explain: "What's the difference between faithfulness and answer relevancy, and when does each fail you?"

### Day 6 — Agent eval + gate + CI
- Read: [`09_AGENT_EVAL.md`](09_AGENT_EVAL.md), [`10_GATE_AND_CI.md`](10_GATE_AND_CI.md)
- Python focus: `argparse`, exit codes, `dataclass(field(default_factory=...))`, `shutil`, `Counter`
- Code: hand-edit `eval/reports/current.json` to trigger each of the five gate failure classes in turn. Run `make gate` and read the markdown each time.
- Break-it: remove a metric from `current.json` entirely — confirm it becomes a *warning*, not a failure. Then decide whether that's the right default and write down your argument.
- Explain: "Design an eval gate for a team shipping an LLM feature weekly."

### Day 7 — Advanced Python consolidation + interview mode
- Read: [`11_ADVANCED_PYTHON.md`](11_ADVANCED_PYTHON.md), [`12_INTERVIEW_DRILLS.md`](12_INTERVIEW_DRILLS.md)
- Code: refactor `app/providers.py` from ABC to `typing.Protocol` and argue which is better here. Add `mypy --strict` to one module and fix the fallout.
- Drill: work the whole question bank out loud, timed. Record yourself on three answers.
- Explain: the 90-second repo pitch, the 5-minute architecture walkthrough, and three STAR stories.

---

## Daily self-check

At the end of each day you should be able to, without looking:

1. Draw the data flow for that layer on a whiteboard.
2. Name the failure mode each component defends against.
3. Point to the test that would catch a regression in it.
4. Name one thing you'd do differently at 100× scale.

If any of the four is shaky, that's tomorrow's first hour.

---

## Reading order for the deep dives

```
01 Foundations
   └─ 02 Ingestion & Embeddings
        └─ 03 Retrieval Pipeline
             └─ 04 RAG Core & Security
                  └─ 05 Agent
                       └─ 06 Observability
                            └─ 07 Eval Harness
                                 ├─ 08 Eval Metrics
                                 └─ 09 Agent Eval
                                      └─ 10 Gate & CI
11 Advanced Python  ← read alongside, section by section
12 Interview Drills ← read last, revisit daily
```
