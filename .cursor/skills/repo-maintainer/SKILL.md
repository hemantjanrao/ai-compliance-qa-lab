---
name: repo-maintainer
description: Maintain and upgrade the AI Compliance QA Lab — run tests, fix CI, tune eval gate and thresholds, promote baseline, upgrade dependencies, add eval tests. Use when fixing gate failures, CI errors, dependency updates, or repo hygiene tasks.
---

# Repo Maintainer — AI Compliance QA Lab

Operate as a careful maintainer. Minimize scope, match existing patterns, run tests before declaring done.

## Startup checklist

1. Read `AGENTS.md` for project map
2. Identify whether the change touches `tests/` (no API) or `eval/` (needs keys)
3. Run the smallest relevant command first:

```bash
make unit                    # always — ~5s, no API keys
make eval-fast               # adversarial + budget + gate
make eval-full               # full suite before merge
make gate                    # gate only (needs current.json from a prior eval run)
```

## Common maintenance workflows

### Gate failed locally or in CI

1. Read `eval/reports/gate-summary.md` or run `make gate`
2. Classify failure type from `eval/gate.py`:
   - `floor.ragas.*` — absolute floor breach in `eval/thresholds.yaml`
   - `regression.ragas.*` — dropped >5pp vs `eval/reports/baseline.json`
   - `regression.latency.*` — p95 up >30%
   - `adversarial.*` — security suite regression
3. Diagnose root cause (prompt, retrieval, model, threshold miscalibration)
4. Fix code or thresholds with justification — do not lower floors to hide bugs
5. Re-run `make eval-fast` or `make eval-full`, then `make gate`
6. Promote baseline only if the new scores represent intentional improvement: `make promote-baseline`

### CI workflow (`.github/workflows/eval-gate.yml`)

| Job | Trigger | What runs |
|-----|---------|-----------|
| `unit` | PR + main | `make unit` |
| `eval-fast` | PR + main | adversarial + budget + gate (non-blocking `|| true` on gate) |
| `eval-gate-pr` | PR | full `pytest eval/` + gate (blocks merge) |
| `eval-full` | main push | full eval + gate + auto `--promote` |

PR gate failures: download `gate-summary` artifact or reproduce with `make eval-full && make gate`.

### Adding a golden test case

**RAG:** add row to `eval/datasets/golden.jsonl` with `id`, question, `expected_answer`, `must_refuse` flag.

**Agent:** add row to `eval/agent/golden_trajectories.jsonl` with `expected_tools`, `must_contain`, `must_not_contain`.

Run targeted test:
```bash
pytest eval/test_ragas.py -v -m eval -k "case_id"
pytest eval/agent/test_tool_selection.py -v -k "case_id"
```

### Adding a threshold

Edit `eval/thresholds.yaml`. Add a comment citing the calibration run. If gate logic changes, update `tests/test_gate.py`.

### Dependency upgrades

1. Check `pyproject.toml` constraints — **langchain must stay 0.3.x** (ragas compatibility)
2. Upgrade in venv: `pip install -e ".[dev]"`
3. `make unit` then `make eval-fast`
4. Document breaking changes in commit message

### Ingest / corpus issues

- PDF lives at `corpus/eu_ai_act.pdf` (gitignored — download manually)
- `make ingest` populates `chroma_db/` (also gitignored)
- Health check: `curl localhost:8000/health` after `make api`

## Files to know

| File | Role |
|------|------|
| `eval/gate.py` | Floor + regression + adversarial gate logic |
| `eval/thresholds.yaml` | Floors and regression limits |
| `eval/reporting.py` | Writes `current.json` from pytest |
| `eval/reports/baseline.json` | Last known-good (committed) |
| `eval/conftest.py` | Eval caching, fixtures, API key skips |
| `Makefile` | Canonical commands — prefer over ad-hoc pytest |
| `tests/test_gate.py` | Unit tests for gate math (no API) |

## Do not

- Commit `.env`, API keys, or corpus PDFs
- Promote baseline to mask a regression
- Upgrade langchain to 0.4+ without verifying ragas
- Add gate logic inside individual eval test files
- Run `make eval-full` when `make unit` or `make eval-fast` would suffice for the change

## Done criteria

- `make unit` passes
- Relevant eval tier passes (`eval-fast` or `eval-full`)
- Gate passes if eval reports were regenerated
- Diff is minimal and matches repo conventions
