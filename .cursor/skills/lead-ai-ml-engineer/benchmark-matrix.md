# Lead AI/ML Engineer Benchmark Matrix

Reference for `lead-ai-ml-engineer`. Compare repo evidence against what **Lead / Staff AI/ML Engineer** roles typically expect for building and operating LLM systems in production (2024–2026).

Rating guide: **Production-ready pattern** / **Lab-appropriate** / **Prototype** / **Not in scope**

---

## 1. Data & retrieval architecture

| Market expectation | Repo anchor | Production-ready if |
|--------------------|-------------|---------------------|
| Document ingestion pipeline | ingest scripts, chunking | reproducible ingest, versioned corpus |
| Chunking strategy with domain rationale | `\nArticle ` separator | can explain recall/precision tradeoff |
| Advanced retrieval | `app/retrieval/` | hybrid BM25+dense, RRF, cross-encoder rerank, query expansion |
| Embedding model choice documented | `app/embeddings.py` | local vs OpenAI tradeoff stated |
| Vector store abstraction | ChromaDB + BM25 index | swap path to managed DB documented |
| Retrieval params (k, mode, filters) | `RAG_RETRIEVAL_MODE`, article metadata | tunable without redeploy |
| Poisoned / adversarial corpus handling | `tests/test_ingest_guards.py` | ingest-time validation |

**Scale signals (usually Lab/Prototype here):** managed vector DB at HA scale, query routing, corpus versioning, retrieval result cache.

---

## 2. Generation & model lifecycle

| Market expectation | Repo anchor | Production-ready if |
|--------------------|-------------|---------------------|
| Provider abstraction | `app/providers.py` | swap model via config |
| Prompt versioning | `promptfoo/`, prompt files | v1 vs v2 regression exists |
| Cost-tiered models | Haiku eval / Sonnet prod pattern in docs | eval vs prod model split intentional |
| Refusal / safety in generation | golden `must_refuse`, guards | refusal is tested, not hope |
| Non-determinism strategy | metamorphic, G-Eval, thresholds | no brittle exact-match on semantics |

**Not in scope:** fine-tuning pipeline, distillation, custom model hosting.

---

## 3. Agent orchestration

| Market expectation | Repo anchor | Production-ready if |
|--------------------|-------------|---------------------|
| ReAct or equivalent loop | `app/agent/` | bounded steps, tool schemas |
| Tool design (read-only first) | search, lookup, risk, fine calc | clear contracts, no hidden side effects |
| Loop / budget guards | max steps, duplicate detection | runaway prevention tested |
| Trajectory observability | Langfuse `tool.*` spans | debug multi-step failures |
| Agent eval beyond final answer | `eval/agent/` | tool selection + trajectory judge |

**Production gaps:** tool auth, idempotency, human-in-the-loop approval, multi-agent coordination.

---

## 4. Serving & API layer

| Market expectation | Repo anchor | Production-ready if |
|--------------------|-------------|---------------------|
| HTTP API | `app/main.py`, `make api` | health check, structured errors |
| Demo UI | `app/streamlit_ui.py` | separate from prod serving path |
| Input validation / DoS guards | `app/guards.py` | length limits enforced |
| Latency awareness | budget tests, gate latency | p95 tracked in eval reports |

**Scale signals:** no rate limiting, authn/z, request queuing, or autoscaling in-repo.

---

## 5. Observability & operations

| Market expectation | Repo anchor | Production-ready if |
|--------------------|-------------|---------------------|
| Distributed tracing | `app/observability.py` | retrieve + generate + agent spans |
| Trace-to-eval debug loop | docs + Streamlit | narrate incident workflow |
| Cost tracking | eval budget tests | spend per suite known |
| No-op offline mode | observability without keys | tests run without Langfuse |

**Gap:** no alerting, SLO dashboards, or on-call runbooks in-repo (expected — document in evolution plan).

---

## 6. Quality subsystem (eval as engineering)

| Market expectation | Repo anchor | Production-ready if |
|--------------------|-------------|---------------------|
| Layered eval pyramid | `docs/EVAL_STRATEGY.md` | unit → reference → rubric → adversarial → gate |
| Deployment gate | `eval/gate.py`, `thresholds.yaml` | floors + baseline regression |
| Tiered CI cost | `eval-fast` vs `eval-full` | PR vs release separation |
| Baseline promotion discipline | `make promote-baseline` | intentional, not accidental |
| Golden datasets as contracts | jsonl files with ids | failures triage to case id |

Lead angle: eval is not "QA team's problem" — it's part of the **release contract**.

---

## 7. Security & compliance (engineering)

| Market expectation | Repo anchor | Production-ready if |
|--------------------|-------------|---------------------|
| OWASP LLM coverage | `eval/test_adversarial.py`, EVAL_STRATEGY map | mapped to tests |
| Regulated-domain features | EU AI Act corpus, risk tier tool | compliance narrative ready |
| Supply chain awareness | `tests/test_supply_chain.py` | pinned critical deps |
| Data handling narrative | gitignored corpus, no PII in golden | secrets/corpus not committed |

**Gap:** formal audit logging, retention policies, model cards — document in Phase 5 governance.

---

## 8. Platform & MLOps maturity

| Topic | Typical Lead ask | Repo status |
|-------|------------------|-------------|
| IaC / env separation | dev/staging/prod | Prototype — local-first |
| Secrets management | vault, GH secrets | Lab — `.env` pattern |
| Feature flags / A/B | prompt/model experiments | Not in scope — promptfoo offline |
| Experiment tracking | W&B, LangSmith | Lab — Langfuse + json reports |
| Model registry | versioned artifacts | Not in scope |
| Load / soak testing | capacity planning | Not in scope |
| DR / backup | vector index recovery | Not in scope |

---

## 9. Technical leadership competencies

What a **Lead** should demonstrate using this repo:

| Competency | Demonstration |
|------------|---------------|
| Tradeoff articulation | Explain Chroma vs Pinecone vs pgvector with numbers |
| Phased delivery | Phase 0 lab → Phase 2 managed retrieval without rewrite |
| Cross-functional alignment | How eval gate becomes release policy with product/legal |
| Mentoring | Assign golden-set ownership; teach debug order on faithfulness failure |
| Incident response | Trace → golden repro → rollback prompt/model → re-gate |
| RFC quality | ADR with eval impact and rollback plan |
| Cost governance | eval-fast on PR, full eval before promote, trajectory cache rationale |

---

## 10. Staff / Lead interview bar (narrative)

Without notes, a **Lead** practicing here should:

1. Whiteboard RAG + agent flows with latency and cost annotations
2. Defend three architecture decisions from `docs/ARCHITECTURE.md` and name when to revisit
3. Describe how eval gate integrates into CI/CD (including workflow_dispatch tradeoff)
4. Explain scaling bottlenecks: embedding throughput, vector DB, LLM rate limits, agent step explosion
5. Contrast "fix retrieval" vs "fix prompt" vs "swap model" with eval signals for each
6. Outline a 90-day plan to take this lab to staging-grade for a compliance Q&A product
7. Answer a leadership behavioral with a concrete eval-gate or baseline-promotion story

If sections 1–6 score **Lab-appropriate+** with a credible Phase 1–3 evolution plan, the repo is **strong portfolio material for Lead AI/ML system design interviews**.
