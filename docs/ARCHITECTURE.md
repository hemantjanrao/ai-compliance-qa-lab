# Architecture

## Goals

1. Demonstrate end-to-end AI QA — from app code to CI gate.
2. Provide a hands-on practice surface for every major AI QA concern.
3. Stay cheap (under €30/month API spend) and reproducible.

## High-level flow

```mermaid
sequenceDiagram
  participant U as User
  participant API as Streamlit / FastAPI
  participant RAG as RAG core
  participant RET as Retrieval pipeline
  participant DB as ChromaDB + BM25
  participant LLM as LLM provider
  participant LF as Langfuse

  U->>API: question
  API->>RAG: answer(question, mode)
  alt advanced (default)
    RAG->>RET: expand query · hybrid search
    RET->>DB: dense + BM25 candidates
    DB-->>RET: chunk candidates
    RET->>RET: RRF fusion · cross-encoder rerank
    RET-->>RAG: top-k chunks
  else basic
    RAG->>DB: vector top-k
    DB-->>RAG: chunks
  end
  RAG->>LLM: grounded prompt
  LLM-->>RAG: answer
  RAG-->>API: answer + chunks + retrieval_mode
  API-->>U: response
  RAG->>LF: trace retrieve · retrieve.hybrid · llm_generate
```

## Agent flow

```mermaid
sequenceDiagram
  participant U as User
  participant API as Streamlit / FastAPI
  participant A as ReAct agent
  participant T as Tools
  participant LLM as Anthropic
  participant LF as Langfuse

  U->>API: question
  API->>A: run_agent (max 8 steps)
  loop ReAct loop
    A->>LLM: messages + tool schemas
    LLM-->>A: tool call or final answer
  opt tool call
    A->>T: search_ai_act · lookup_article · check_risk_tier · compute_fine
    T-->>A: tool result
  end
  end
  A-->>API: answer + trajectory
  API-->>U: response
  A->>LF: trace (run_agent, tool.*)
```

## Component decisions

| Choice | Rationale | Alternative considered |
|---|---|---|
| ChromaDB | Local, no infra, persistent | Pinecone (cost), pgvector (overhead) |
| **Advanced retrieval** (`app/retrieval/`) | Hybrid BM25 + dense, RRF fusion, cross-encoder rerank, query expansion | Basic vector-only (still available via `RAG_RETRIEVAL_MODE=basic`) |
| RecursiveCharacterTextSplitter with `\nArticle ` separator | Preserves legal structure | Semantic chunking (slower, marginal gain) |
| Local or OpenAI embeddings (`app/embeddings.py`) | Default local (`all-MiniLM-L6-v2`) — $0 ingest; OpenAI optional | OpenAI-only (higher cost at ingest scale) |
| Two providers wired from day 1 | Provider diversity is an interview signal | Single provider (less work but weaker story) |
| Claude Haiku for eval, Sonnet for prod | Cost control | Always-Sonnet (3-5x cost) |
| RAGAS + DeepEval + promptfoo | Each covers a different angle | Pick one (less interview surface area) |
| Trajectory cache in eval | Cuts agent CI cost ~4× | Re-run agent per assertion (wasteful) |

## Eval strategy

See `docs/EVAL_STRATEGY.md` for the full pyramid. Summary:

```mermaid
flowchart BT
  Unit["1. Unit tests (tests/)\ntools · gate · poisoned RAG · retrieval"]
  Ref["2. Reference metrics (RAGAS)\n8 single-turn metrics"]
  Rubric["3. DeepEval\nbuilt-in + G-Eval + agent"]
  Prop["4. Property-based\nmetamorphic · bias"]
  Adv["5. Adversarial\nOWASP LLM Top 10"]
  PF["6. promptfoo\nprompt v1 vs v2"]
  Gate["7. Gate (eval/gate.py)\nfloors + regression vs baseline"]

  Unit --> Ref --> Rubric --> Prop --> Adv --> PF --> Gate
```

1. **Unit tests** (`tests/`) — tools, gate math, poisoned retrieval, retrieval fusion. No API keys.
2. **Reference metrics** (RAGAS) — 8 single-turn metrics (faithfulness, relevancy, precision, recall, correctness, similarity, entity recall, context relevance).
3. **Custom rubrics** (DeepEval) — 6 built-in RAG metrics + 4 G-Eval rubrics + 3 agent metrics.
4. **Property-based** — paraphrase + demographic invariance via embeddings.
5. **Adversarial** — OWASP categories + agent-specific attacks.
6. **Prompt regression** (promptfoo) — full golden-set prompt v1 vs v2.
7. **Gate** (`eval/gate.py`) — absolute floors + regression vs `eval/reports/baseline.json`.

## CI pipeline

```mermaid
flowchart TD
  subgraph EveryPush["Every PR / push to main"]
    U[unit · 5s · $0]
    EF[eval-fast · adversarial + budget + gate]
    U --> EF
  end

  subgraph Manual["Manual: GitHub Actions → Eval Gate"]
    Full[eval-full · full pytest + gate]
    Promote[promote baseline · checkbox]
    Full --> Promote
  end
```

Fast PR feedback on unit tests; `eval-fast` runs adversarial + budget when API secrets are set. Full eval (RAGAS, DeepEval, agent, promptfoo) is **workflow_dispatch only** — blocks regression only when you run it.

## Handling non-determinism

- **Embedding similarity** for semantic equivalence
- **LLM-as-judge with calibrated rubric** for nuanced criteria
- **Keyword markers** only for binary properties (refusals)
- **Trajectory caching** (`EVAL_USE_CACHE=1`) for agent eval stability

## Observability

`app/observability.py` wraps RAG and agent calls in Langfuse traces when `LANGFUSE_*` keys are set. No-op without keys (unit tests, offline dev).

Traced spans: `retrieve`, `retrieve.hybrid`, `answer`, `llm_generate`, `run_agent`, `tool.*`

## Cost model

| Command | Approx cost |
|---------|-------------|
| `make unit` | $0 |
| `make eval-fast` | $0.10–0.30 |
| `make eval-full` | $1.50–2.50 |

## Repository map

```
app/
  rag.py              RAG retrieve + generate
  retrieval/          Hybrid BM25 + vector, RRF, cross-encoder rerank
  observability.py    Langfuse traces (no-op without keys)
  agent/              ReAct loop + 4 tools
  providers.py        Anthropic / OpenAI abstraction
  streamlit_ui.py     RAG + Agent + Eval scorecard tabs
eval/
  gate.py             Baseline comparison gate
  reporting.py        Metric collection → current.json
  thresholds.yaml     Floors + gate tolerances
  conftest.py         Agent trajectory cache
tests/                Fast unit tests
```

## Advanced retrieval (Phase 2)

When `RAG_RETRIEVAL_MODE=advanced` (default):

```mermaid
flowchart TD
  Q[Question] --> E[Query expansion]
  E --> V[Dense search Chroma]
  E --> B[BM25 sparse search]
  V --> RRF[Reciprocal Rank Fusion]
  B --> RRF
  RRF --> CE[Cross-encoder rerank]
  CE --> C[Top-k chunks → prompt]
```

Set `RAG_RETRIEVAL_MODE=basic` to restore naive vector-only retrieval.

## What's intentionally out of scope

- Fine-tuning
- Managed vector DB (Pinecone / pgvector HA)
- Multi-modal
- Multi-agent orchestration
- Tool side effects (email, DB writes) — read-only tools only
