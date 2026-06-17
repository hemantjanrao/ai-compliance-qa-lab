# AI QA Market Benchmark Matrix

Reference for `ai-qa-stack-review`. Compare repo evidence against what **Senior AI QA Engineer** job postings and staff-level interviews typically expect (2024–2026).

Rating guide: **Strong** / **Adequate** / **Partial** / **Gap**

---

## 1. RAG evaluation

| Market expectation | Repo anchor | Strong if |
|------------------|-------------|-----------|
| RAGAS or equivalent reference metrics | `eval/test_ragas.py`, `eval/ragas_config.py` | faithfulness, relevancy, precision, recall run on golden set |
| Golden dataset with refusal / edge cases | `eval/datasets/golden.jsonl` | 15+ cases, `must_refuse`, tagged by topic |
| Per-provider eval (model comparison) | anthropic + openai in tests | both providers scored and gated |
| Retrieval-debug workflow | `app/rag.py`, Langfuse spans | can explain k, chunking, embed model impact |

**Partial/Gap signals:** no golden set; only manual spot checks; no context-level asserts.

---

## 2. Custom metrics & LLM-as-judge

| Market expectation | Repo anchor | Strong if |
|------------------|-------------|-----------|
| G-Eval / rubric judges beyond RAGAS | `eval/test_deepeval.py` | citation + refusal rubrics with thresholds |
| Trajectory / path quality judge | `eval/agent/test_trajectory_judge.py` | judges agent *path*, not just final answer |
| Judge config separated from app | `eval/ragas_config.py` | swap judge model without app code change |

---

## 3. Agent QA

| Market expectation | Repo anchor | Strong if |
|------------------|-------------|-----------|
| Tool selection accuracy | `eval/agent/test_tool_selection.py` | expected_tools per golden case |
| Loop / budget guards | step limits, duplicate detection | tests fail bad trajectories |
| Agent adversarial | `eval/agent/test_adversarial.py` | injection, hallucinated tools |
| Trajectory caching for CI cost | `eval/conftest.py` | can explain why cache exists |

**Gap signals:** only end-to-end answer checks; no multi-step assertions.

---

## 4. Security & red team (OWASP LLM)

| Market expectation | Repo anchor | Strong if |
|------------------|-------------|-----------|
| Prompt injection suite | `eval/test_adversarial.py` | parametrized probes, multi-provider |
| PII / disclosure probes | same | explicit extraction attempts |
| Poisoned retrieval | `tests/test_rag_security.py` | unit-level vector weakness |
| Supply chain awareness | `tests/test_supply_chain.py` | pinned critical deps |
| Ingest poisoning guards | `tests/test_ingest_guards.py` | rejects bad corpus |
| Input DoS / length limits | `app/guards.py`, `tests/test_input_guards.py` | max length enforced |
| Automated scanner (garak etc.) | `scripts/garak_scan.sh`, `make garak-redteam` | script exists (CI optional) |

Map coverage to OWASP table in `docs/EVAL_STRATEGY.md`.

---

## 5. Non-determinism & fairness

| Market expectation | Repo anchor | Strong if |
|------------------|-------------|-----------|
| Metamorphic / paraphrase invariance | `eval/test_metamorphic.py` | embedding similarity thresholds |
| Bias / demographic invariance | `eval/test_bias.py` | paired prompts, semantic compare |
| No brittle exact-string asserts on semantics | across `eval/` | uses floors, embeddings, judges |

---

## 6. Eval gate & CI engineering

| Market expectation | Repo anchor | Strong if |
|------------------|-------------|-----------|
| Absolute quality floors | `eval/thresholds.yaml` | per-metric floors with comments |
| Regression vs baseline | `eval/gate.py`, `eval/reports/baseline.json` | 5pp drop detection |
| Latency / cost regression | `eval/test_budget.py`, gate latency checks | p95 tracked |
| Tiered CI (fast vs full) | `Makefile`, `eval-gate.yml` | PR: unit + eval-fast; full eval via workflow_dispatch |
| Promotion workflow | `make promote-baseline` | deliberate baseline updates |
| Unit tests for gate math | `tests/test_gate.py` | no API keys for gate logic |

**Senior interview angle:** "floors catch catastrophes; baseline catches drift."

---

## 7. Observability & debug loop

| Market expectation | Repo anchor | Strong if |
|------------------|-------------|-----------|
| Trace per request | `app/observability.py` | retriever + generation spans |
| Connect trace → eval failure | docs + Streamlit | can narrate debug order |
| LangSmith-equivalent concepts | `docs/ALLIANZ_SUPPLEMENT.md` | maps Langfuse → LangSmith |

**Gap:** no hosted LangSmith project in-repo (expected).

---

## 8. Prompt & config regression

| Market expectation | Repo anchor | Strong if |
|------------------|-------------|-----------|
| Prompt versioning / A-B prompts | `promptfoo/promptfooconfig.yaml` | v1 vs v2 comparison |
| Config-driven eval | promptfoo + golden sets | non-dev can trigger eval |

**Partial:** A/B traffic splitting not implemented — theory only in supplement.

---

## 9. E2E & API testing

| Market expectation | Repo anchor | Strong if |
|------------------|-------------|-----------|
| API surface | `app/main.py`, `make api` | health + RAG endpoints |
| UI smoke / E2E | `tests/e2e/`, Playwright in dev deps | `make e2e-ui` exists |
| FastAPI contract tests | `tests/` | basic route tests if present |

---

## 10. Test architecture & data

| Market expectation | Repo anchor | Strong if |
|------------------|-------------|-----------|
| Test pyramid documented | `docs/EVAL_STRATEGY.md` | unit → integration → slow judge |
| Pytest markers for cost control | `pyproject.toml` markers | eval / adversarial / slow |
| Separation: measure vs gate | `eval/reporting.py` vs `eval/gate.py` | tests don't embed gate logic |
| Golden case IDs for triage | jsonl `id` fields | failures map to case id |

---

## 11. Domain & compliance context

| Market expectation | Repo anchor | Strong if |
|------------------|-------------|-----------|
| Regulated-domain RAG | EU AI Act corpus | refusal, risk tier, citations |
| Ethics / governance narrative | golden refusals, agent tools | interview story ready |

Adds credibility for finance/insurance roles; not a substitute for legal review.

---

## 12. Enterprise gaps (usually Partial/Gap in any lab)

Study via `docs/ALLIANZ_SUPPLEMENT.md` — do not penalize the repo harshly if these are documented as extensions:

| Topic | Typical market ask | Repo status |
|-------|-------------------|-------------|
| LangSmith / W&B experiments | Managed eval UI | Partial — Langfuse only |
| ISTQB CT-AI vocabulary | Certification language | Partial — supplement flashcards |
| Live A/B + feature flags | Production experimentation | Gap — narrative only |
| Spec-driven QA (OpenSpec, etc.) | AC → golden mapping | Partial — pattern shown |
| SBOM / Dependabot | Supply chain ops | Partial — unit pin tests |
| Multimodal / speech / vision eval | Broader AI surface | Gap |
| Load / soak testing | Scale QA | Gap |
| Human-in-the-loop eval | Rater workflows | Gap |

---

## Senior competency bar (narrative)

A **senior** practicing here should be able to **without notes**:

1. Draw the eval pyramid and name which file implements each layer
2. Explain faithfulness vs context_recall failure modes and debug order
3. Describe gate floors vs baseline regression with numbers (5pp, 30% latency)
4. Contrast RAG testing vs agent testing (path vs destination)
5. Map three OWASP items to specific test files
6. Walk through promoting a baseline after an intentional model change
7. Name two enterprise gaps and how they'd extend this lab in production

If the repo scores **Adequate+** on sections 1–6 and documents 7–12, it is **market-aligned for senior AI QA practice**.
