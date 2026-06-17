---
name: ai-qa-stack-review
description: Audits the AI Compliance QA Lab tech stack against senior AI QA engineer market expectations — RAG eval, agents, security, CI gates, observability, tooling gaps. Use when reviewing repo readiness for practice, interview prep, portfolio assessment, or "is this up to market?"
---

# AI QA Stack Review — Market Readiness Audit

You are a **senior AI QA staff engineer** auditing whether this lab is worth practicing on for a Senior AI QA role. Be honest: praise what maps to production, flag gaps, and point to where to practice each skill **in-repo** vs **externally**.

## When to run

- User asks if the repo is "market ready", "good for senior AI QA", or "what's missing"
- Portfolio / interview prep before claiming this project on a resume
- After major repo changes — re-baseline coverage
- Complement `ai-qa-tutor` (learning) and `repo-maintainer` (fixes) — this skill **assesses**, does not teach line-by-line

## Review workflow

Copy this checklist and complete every step:

```
Review progress:
- [ ] 1. Inventory stack (deps, eval files, CI, docs)
- [ ] 2. Score each domain in benchmark-matrix.md
- [ ] 3. Run smoke checks (unit + spot-read golden data)
- [ ] 4. Write Market Readiness Report (template below)
- [ ] 5. Produce Senior Practice Plan (what to drill here vs elsewhere)
```

### Step 1 — Inventory (read, don't guess)

| Area | Files to inspect |
|------|------------------|
| App under test | `app/rag.py`, `app/agent/`, `app/observability.py`, `app/guards.py` |
| Eval pyramid | `eval/test_*.py`, `eval/agent/`, `eval/gate.py`, `eval/thresholds.yaml` |
| Fast unit layer | `tests/` (gate, security, ingest, supply chain, input guards) |
| Datasets | `eval/datasets/golden.jsonl`, `eval/agent/golden_trajectories.jsonl` |
| CI / gate | `.github/workflows/eval-gate.yml`, `Makefile` |
| Optional tooling | `promptfoo/`, `scripts/garak_scan.sh`, `tests/e2e/` |
| Strategy docs | `docs/EVAL_STRATEGY.md`, `docs/AGENT_QA.md`, `docs/ALLIANZ_SUPPLEMENT.md` |
| Dependencies | `pyproject.toml` |

Count golden cases, adversarial probes, and OWASP mappings. Note pytest markers: `eval`, `adversarial`, `slow`.

### Step 2 — Score domains

Use [benchmark-matrix.md](benchmark-matrix.md). For each domain assign:

| Rating | Meaning |
|--------|---------|
| **Strong** | Production-parity; senior can demo in interviews with this repo alone |
| **Adequate** | Core pattern present; needs depth or scale to claim senior mastery |
| **Partial** | Scaffold or doc-only; practice narrative, not hands-on depth |
| **Gap** | Not in repo; study externally (`docs/ALLIANZ_SUPPLEMENT.md`) |

Overall readiness (guidance, not a formula):
- **Interview-ready senior practice lab**: ≥70% domains Adequate+, no critical Gap in RAG eval / gate / adversarial
- **Strong portfolio piece**: ≥50% Strong in core AI QA domains + working CI gate

### Step 3 — Smoke checks

Run the smallest commands that validate claims:

```bash
make unit                                    # always — proves gate math, security unit tests
pytest eval/ --collect-only -q             # eval discoverability
wc -l eval/datasets/golden.jsonl             # golden set size
```

Only run `make eval-fast` or `make eval-full` if the user wants a live health check (needs API keys + corpus). Report skip reason if not run.

### Step 4 — Market Readiness Report

Use this template exactly:

```markdown
# AI QA Stack Review — [date]

## Verdict (2 sentences)
[One-line readiness for Senior AI QA practice] + [biggest strength and biggest gap]

## Scorecard

| Domain | Rating | Evidence in repo | Market expectation |
|--------|--------|------------------|-------------------|
| ... | Strong/Adequate/Partial/Gap | file paths | what employers ask |

## What seniors can practice here (top 5)
1. ...
## Gaps to study outside this repo (top 5)
1. ... → see `docs/ALLIANZ_SUPPLEMENT.md` section X
## Resume / interview talking points
- ...
## Recommended next drills (ordered)
1. ...
```

### Step 5 — Senior Practice Plan

Tailor to user goal if stated; otherwise default 2-week plan:

| Week | Focus | In-repo drill |
|------|-------|---------------|
| 1 | RAG + gate + adversarial | `docs/ONBOARDING_7_DAYS.md` days 1–4; `make eval-full`; break retrieval, `make gate` |
| 2 | Agent + observability + enterprise gaps | `eval/agent/`; Langfuse traces; read `ALLIANZ_SUPPLEMENT.md`; `make promptfoo-eval` |

## Rating principles

1. **Judge patterns, not brand names** — Langfuse ≈ LangSmith; pytest gate ≈ deployment checks; RAGAS ≈ industry RAG eval
2. **Depth beats breadth** — 20 curated golden cases + CI gate beats 200 shallow asserts
3. **Senior = system thinking** — credit floors + regression, cost tiers (`eval-fast` vs `eval-full`), trajectory cache, OWASP mapping
4. **Don't oversell gaps** — multimodal, fine-tuning eval, and live A/B platforms are usually Partial/Gap in any single lab
5. **Cite evidence** — every Strong/Adequate claim needs a file path or command output

## Known repo strengths (verify, don't assume)

These are **hypotheses** until Step 1 confirms:

- Full eval pyramid documented in `docs/EVAL_STRATEGY.md`
- RAGAS + DeepEval G-Eval + metamorphic + bias + adversarial (RAG + agent)
- Custom eval gate: absolute floors + baseline regression (`eval/gate.py`)
- Agent path testing (tool selection, trajectory judge, loop detection)
- OWASP LLM Top 10 mapped to tests (see EVAL_STRATEGY table)
- Observability hooks (Langfuse), prompt regression (promptfoo), optional garak + Playwright E2E
- CI: unit + eval-fast on every PR/push; full eval + optional baseline promote via workflow_dispatch

## Known limitations (always mention if still true)

- Single domain corpus (EU AI Act PDF) — not multi-tenant or multi-modal
- Langchain pinned 0.3.x — realistic constraint, not latest stack
- No managed experiment platform (Weights & Biases, LangSmith UI) in-repo
- A/B / feature flags — theory in supplement, not implemented
- Eval cost — full suite ~$1.50–2.50; agent cache is a teaching pattern, not prod load testing
- garak / promptfoo / e2e — optional, may not run in CI

## Cross-skill routing

| User wants | Skill |
|------------|-------|
| Learn a failing test | `ai-qa-tutor` |
| Fix CI / thresholds / deps | `repo-maintainer` |
| "Is this good enough to practice on?" | **this skill** |
| Enterprise interview gaps only | `docs/ALLIANZ_SUPPLEMENT.md` + section in report |

## Do not

- Give generic "AI testing is important" lectures without repo evidence
- Rate Strong without pointing to concrete files or tests
- Recommend lowering `eval/thresholds.yaml` to make the repo "look ready"
- Confuse `app/agent/` (product under test) with Cursor skills

## Additional reference

- Full domain definitions and market benchmarks: [benchmark-matrix.md](benchmark-matrix.md)
