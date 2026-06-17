# Allianz AI QA — Supplement Guide

Skills needed for enterprise AI QA roles (e.g. Allianz Global Investors AI QA Engineer) that extend beyond the core eval pyramid in this repo. **Practice the core here first** (`ONBOARDING_7_DAYS.md`); use this doc for gaps and interview polish.

---

## Coverage map

| Skill | Practiced in this repo | This supplement |
|-------|---------------------|-----------------|
| RAGAS + golden sets | `eval/test_ragas.py`, `golden.jsonl` | — |
| G-Eval / LLM-as-judge | `eval/test_deepeval.py` | — |
| Agent trajectory QA | `eval/agent/` | — |
| OWASP LLM01–02, 06–09 | `eval/test_adversarial.py` | — |
| OWASP LLM03 supply chain | `tests/test_supply_chain.py` | SBOM narrative below |
| OWASP LLM04 ingest poisoning | `tests/test_ingest_guards.py` | Ingest checklist below |
| OWASP LLM05 DoS | `app/guards.py`, `tests/test_input_guards.py` | Rate limits below |
| CI quality gates | `eval/gate.py` | — |
| Langfuse observability | `app/observability.py` | LangSmith mapping below |
| Prompt regression | `promptfoo/` | `make promptfoo-eval` |
| Automated red team | `scripts/garak_scan.sh` | `make garak-redteam` |
| API / UI E2E | `tests/e2e/` | `make e2e-ui` |
| ISTQB CT-AI vocabulary | — | Flashcards below |
| A/B testing + feature flags | — | Narrative below |
| Spec-driven QA | — | Framework mapping below |

---

## LangSmith ↔ Langfuse (45 min)

Same architecture, different vendor. After using Langfuse in this lab, read [LangSmith evaluation docs](https://docs.smith.langchain.com/evaluation).

| Concept | This repo (Langfuse) | LangSmith |
|---------|---------------------|-----------|
| Trace per request | `trace()` in `app/observability.py` | `@traceable` / run trees |
| Span types | retriever, generation, tool, agent | chain, llm, retriever, tool |
| Eval dataset | `eval/datasets/golden.jsonl` | LangSmith datasets |
| Eval run artifact | `eval/reports/current.json` | Experiment runs |
| CI gate | `make gate` | Dataset evaluators + deployment checks |

**Interview line:** "I've implemented the Langfuse pattern — traces, golden datasets, automated evals, regression gates. LangSmith is the same workflow in the LangChain ecosystem."

---

## ISTQB CT-AI flashcards (1 hr)

| Ch | Topic | AI QA hook in this lab |
|----|-------|------------------------|
| 1 | AI system types | RAG (`app/rag.py`) vs agent (`app/agent/`) vs classifier tools |
| 2 | ML vs GenAI testing | No exact-string asserts; semantic metrics |
| 3 | AI risks | Hallucination → faithfulness; security → adversarial suite |
| 4 | Test levels | Unit (`tests/`) → integration (`eval/`) → acceptance (golden set) |
| 5 | Test design | Golden tags = equivalence classes; Article 999 = boundary |
| 6 | Non-functional | `latency` + `cost` in `eval/thresholds.yaml` |
| 7 | Test data | `golden.jsonl`, adversarial strings, poisoned chunk |
| 8 | Test automation | pytest markers, CI gate, `EVAL_USE_CACHE` |
| 9 | AI quality chars | Faithfulness, relevancy, robustness, fairness (bias test) |
| 10 | Ethics / governance | EU AI Act domain, refusal cases, risk-tier tool |

---

## A/B testing + feature flags (30 min theory)

Enterprise AI experimentation maps to eval gates:

```
Variant A (control)          Variant B (new prompt/model)
        \                            /
         \── same golden.jsonl ───/
                      │
               pytest eval suite
                      │
              compare vs baseline
                      │
         gate passes → flip feature flag
         gate fails  → block rollout
```

| Concept | AI QA implementation |
|---------|---------------------|
| Feature flag | Run eval on both variants before enabling flag |
| A/B test | Split traffic; monitor faithfulness + refusal rate distributions |
| Canary | 5% traffic + continuous eval on golden subset |
| Guardrail | `make gate` blocks promotion |

**Interview line:** "A/B for AI compares metric distributions on a golden eval set, not click-through. Variant B must pass the same gate as A before the feature flag flips."

---

## Spec-driven QA (30 min)

Job postings mention OpenSpec, GitHub Spec Kit, Tessl. Pattern:

1. **Spec** — user story + acceptance criteria
2. **Golden case** — `question`, `expected_answer`, `must_refuse`, `tags`
3. **Automated assert** — RAGAS floor, G-Eval rubric, or refusal heuristic

Example spec → test mapping:

| Spec acceptance criterion | Golden field | Assert |
|---------------------------|--------------|--------|
| Must cite Article 5 for prohibited practices | `rag-002` | G-Eval citation metric |
| Must refuse financial advice | `rag-022` | `must_refuse: true` + adversarial heuristic |
| Agent must use lookup for article questions | `golden_trajectories.jsonl` | `expected_tools` |

**Exercise:** Pick one golden case and write the spec acceptance criteria above it in your notes.

---

## OWASP LLM03–05 (extended)

| OWASP | Risk | Repo coverage | Production extension |
|-------|------|---------------|---------------------|
| LLM03 Supply chain | Compromised deps | `tests/test_supply_chain.py` pins | SBOM, Dependabot, signed packages |
| LLM04 Data poisoning | Bad training/ingest data | `tests/test_ingest_guards.py` | Source verification, chunk audit logs |
| LLM05 DoS | Huge prompts | `app/guards.py` max length | Rate limits, token budgets per user |

---

## Optional tooling commands

```bash
# Prompt regression (prompt v1 vs v2)
make promptfoo-eval

# garak automated red-team scan (~$0.10 on Haiku)
make garak-redteam

# Fast API smoke (no API keys)
pytest tests/e2e/test_api_smoke.py -v

# Streamlit UI (requires: make serve + playwright install chromium)
E2E_UI=1 make e2e-ui
```

---

## Gate drill (repeat until automatic)

```bash
cp eval/reports/baseline.json eval/reports/current.json
# Edit current.json: drop ragas.anthropic.faithfulness to 0.70
make gate    # expect FAIL (floor + regression)
rm eval/reports/current.json
```

---

## Langfuse checklist

1. Keys in `.env` (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`)
2. `make serve` → one RAG query + one agent query
3. Langfuse UI → trace → retriever → generation → tool spans
4. Screenshot for portfolio

---

## Interview portfolio sentence

> "I built a CI-gated RAG + agent eval suite on EU AI Act compliance: 23-case golden set, RAGAS + G-Eval, OWASP adversarial tests (including supply-chain pins, ingest guards, input limits), Langfuse traces, promptfoo regression, and floor + baseline regression gates."

---

## Suggested order

1. Finish `ONBOARDING_7_DAYS.md`
2. Run `make eval-full` once
3. Langfuse screenshot + gate drill
4. Read this doc sections 1–4 (LangSmith, ISTQB, A/B, spec-driven)
5. Optional: `make garak-redteam`, `make promptfoo-eval`, `E2E_UI=1 make e2e-ui`
