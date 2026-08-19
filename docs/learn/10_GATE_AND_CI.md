# 10 — The Eval Gate and CI

Files: `eval/gate.py` (337 lines — the largest single file in the repo), `eval/thresholds.yaml`, `eval/reports/baseline.json`, `tests/test_gate.py`, `.github/workflows/eval-gate.yml`, `Makefile`

This is the layer that turns measurement into a decision. It's also the most frequently asked-about topic in senior AI QA interviews, because it's where "we evaluate our LLM" becomes "we have a quality bar that blocks merges."

---

## 1. The pattern

From `eval/gate.py`'s docstring:

> *"this is the production pattern interviewers ask about:*
> *1. Run eval harness → produce artifact (current.json)*
> *2. Compare to last-known-good baseline*
> *3. Block merge if regression exceeds tolerance"*

```
eval/thresholds.yaml ─┐
eval/reports/baseline.json ─┤
eval/reports/current.json ──┴─► compare_reports() ─► GateResult ─► exit 0 / 1
                                                              └─► gate-summary.md
```

`compare_reports` is a **pure function of two dicts plus config**. No I/O, no network, no LLM. That's what makes `tests/test_gate.py` possible — the gate itself is unit-tested with hand-written fixtures.

> **Interview line:** "The gate is a pure function over two JSON artifacts. That means we unit-test our quality gate the same way we unit-test business logic — with fixtures, in milliseconds, for free. A gate you can't test is a gate you can't trust."

---

## 2. The five check classes

| # | Check | Compares against | Catches |
|---|---|---|---|
| 1 | **Absolute floor** | `thresholds.yaml` | "Never ship below this bar", even on a fresh baseline |
| 2 | **Relative regression** | `baseline.json` | "Don't get meaningfully worse than last known good" |
| 3 | **Latency regression** | `baseline.json` (relative %) | Performance regressions |
| 4 | **promptfoo pass rate** | both floor and baseline | Prompt regressions |
| 5 | **Adversarial stickiness** | `baseline.json` | Security regressions |

### Why floors AND regression — the key insight

They catch different things:

- **Floor only:** you could slide from 0.95 → 0.81 while staying above a 0.80 floor. That's a 14-point collapse the gate never sees.
- **Regression only:** you could drift down 4 points per PR, forever, never tripping the 5-point tolerance. Death by a thousand cuts, and the baseline moves with you each time you promote.

**Together:** a hard bar you can never cross, plus a rate limit on how fast you can approach it.

> **Interview line:** "A floor alone permits a slow slide; a regression check alone permits an unlimited drift as long as each step is small. You need both — an absolute quality bar and a rate limit on degradation."

### Check 1 — floors

```python
for provider in PROVIDERS:
    for metric in RAGAS_METRICS:
        value = (current.get("ragas") or {}).get(provider, {}).get(metric)
        floor = ragas_floor.get(metric)
        if value is None or floor is None:
            result.warnings.append(f"Skipping floor check: ragas.{provider}.{metric} (missing data)")
            continue
        if value < floor:
            result.passed = False
            result.failures.append(GateFailure(
                check=f"floor.ragas.{provider}.{metric}",
                message=f"{metric}={value:.3f} below floor {floor:.3f}"))
```

The `check` field uses a **structured dotted name** — `floor.ragas.anthropic.faithfulness`. Machine-parseable, greppable, and it tells you the check type, the framework, the provider, and the metric in one token. This is a small thing that makes CI output actually usable.

Applied to four metric families with the same shape: RAGAS (per provider), DeepEval provider metrics (per provider), DeepEval agent metrics (global), promptfoo `pass_rate`.

### Check 2 — regression

```python
def _metric_drop(baseline: float, current: float) -> float:
    return baseline - current

drop = _metric_drop(b, c)
if drop > max_metric_drop:                      # default 0.05 from thresholds.yaml
    result.failures.append(GateFailure(
        check=f"regression.ragas.{provider}.{metric}",
        message=f"{metric} dropped {drop:.3f} ({b:.3f} → {c:.3f}), limit {max_metric_drop:.3f}"))
```

**Absolute difference in the score, not relative percentage.** For a metric bounded in [0,1] this is the right choice — "faithfulness dropped 5 points" is meaningful at any level, whereas "dropped 5%" means something different at 0.9 than at 0.5.

**Improvements are never blocked.** `drop` is negative when current > baseline. The gate is one-sided by design. (A two-sided gate that flags suspicious *improvements* is a real thing in some ML teams — worth mentioning as a possible extension.)

The message shows `before → after` and the limit. **Every failure message should let you make a decision without opening another tool.**

### Check 3 — latency

```python
def _latency_increase(baseline: float, current: float) -> float:
    if baseline <= 0:
        return 0.0
    return (current - baseline) / baseline

inc = _latency_increase(b, c)
if inc > max_latency_increase:                  # default 0.30
    ... f"p95 latency up {inc:.1%} ({b:.0f}ms → {c:.0f}ms), limit {max_latency_increase:.1%}"
```

**Relative, not absolute** — the opposite choice from quality metrics, and for a good reason. Latency has no natural bound and its baseline shifts with hardware, model, and network. "30% slower" stays meaningful whether the baseline is 500ms or 5s.

`if baseline <= 0: return 0.0` guards division by zero.

Note the format specs: `{inc:.1%}` renders `0.35` as `35.0%`; `{b:.0f}ms` drops decimals from milliseconds. Readable output is not a nicety in CI.

### Check 5 — adversarial stickiness

```python
for suite in ("rag_passed", "agent_passed"):
    if baseline.get("adversarial", {}).get(suite) is True:
        if current.get("adversarial", {}).get(suite) is not True:
            result.passed = False
            result.failures.append(GateFailure(
                check=f"adversarial.{suite}",
                message=f"Adversarial suite {suite} was passing on baseline but not on current run"))
```

**A ratchet.** Once security tests pass on a baseline, they must keep passing. There is no tolerance, no percentage, no tradeoff.

Note `is not True` rather than `== False` — this catches `None` (didn't run / no keys) as well as `False`. **Not running your security tests is treated the same as failing them.** That is the correct default, and it's a strong detail to point out.

> **Interview line:** "Quality metrics have tolerances because they're noisy. Security assertions don't — they're binary and they ratchet. And 'we didn't run them' counts as a failure, not a pass."

---

## 3. Warnings vs failures — the honest weakness

```python
if value is None or floor is None:
    result.warnings.append(f"Skipping floor check: ... (missing data)")
    continue
```

Missing data produces a **warning**, not a failure. The rationale is sound: a partial run (`eval-fast`, or a run with one provider's key) shouldn't fail on metrics it never computed.

**The risk is equally real:** if a metric silently stops being recorded — a typo, a test that errors before `ReportCollector.set`, a renamed key — the gate degrades to warnings and passes. **You'd believe you're gated when you're not.**

Two concrete instances in this repo:

1. `eval/test_deepeval.py` asserts inside the per-case loop, so the first failure skips `ReportCollector.set` entirely → that metric becomes "missing data" → a warning. **A hard-failing metric becomes invisible to the gate.** (The test itself still fails, so CI goes red — but the gate summary won't say why.)
2. The current `baseline.json` contains only 4 of 8 RAGAS metrics and 2 of 10 DeepEval metrics, so most regression checks currently produce warnings.

**Mitigation to propose:** a "required metrics" list — if a named metric is absent from `current.json` on a full run, fail rather than warn. Two-tier: `eval-fast` warns, `eval-full` requires.

This is exactly the kind of thing to raise unprompted in an interview. It shows you read the code critically rather than admiringly.

---

## 4. Result types

```python
@dataclass
class GateFailure:
    check: str
    message: str

@dataclass
class GateResult:
    passed: bool
    failures: list[GateFailure] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
```

- **Structured, not strings.** `failures` can be counted, filtered by prefix, or exported to a dashboard.
- **`field(default_factory=list)`** — the mutable-default rule again.
- **`passed` is set imperatively** as checks run, rather than derived (`len(failures) == 0`). Derivation would be cleaner and remove the possibility of the two disagreeing. Minor design nit worth spotting.
- **Collect all failures, don't short-circuit.** One gate run tells you everything that's wrong. Fail-fast here would mean N CI runs to find N problems.

---

## 5. The CLI

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval gate — baseline comparison")
    parser.add_argument("--baseline", type=Path, default=BASELINE_REPORT)
    parser.add_argument("--current", type=Path, default=CURRENT_REPORT)
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args(argv)
    ...
    return 0 if result.passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
```

Five things worth naming:

1. **`argv: list[str] | None = None`** — testable. `main(["--promote"])` works in a test; `None` falls through to `sys.argv`. Standard pattern, frequently omitted.
2. **`type=Path`** — argparse converts the string for you.
3. **Returns an int; `SystemExit(main())` at the boundary.** The function is pure-ish and testable; only the module-level guard touches process state. `raise SystemExit(...)` is preferred over `sys.exit(...)` in this position.
4. **Exit code IS the CI contract.** `0` = merge, `1` = blocked. `make gate` fails the build automatically because `make` propagates non-zero exit codes.
5. **`--markdown` writes an artifact** for PR comments and CI summaries, in addition to stdout.

### Promotion

```python
if args.promote:
    if not args.current.exists():
        print(f"ERROR: no current report at {args.current}", file=sys.stderr)
        return 1
    args.baseline.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(args.current, args.baseline)
    print(f"Promoted {args.current} → {args.baseline}")
    return 0
```

A literal file copy. The important part is the **policy** around it, from `AGENTS.md`:

> *"`eval/reports/baseline.json` **is** committed — treat promotion as a deliberate release decision"*

And `.gitignore` excludes `current.json` and `gate-summary.md` (generated) while `baseline.json` is tracked.

**This means promoting the baseline is a reviewed commit.** Someone must look at a diff showing the metric values changing. That's the control that prevents "the gate keeps failing, let me just promote."

⚠️ Note `--promote` does **not** verify the gate passed first. `make promote-baseline` runs it unconditionally. The CI workflow guards it with `if: inputs.promote_baseline` on a manual dispatch after a green `eval-full`, but locally nothing stops you promoting a bad run. **Adding a gate check inside `--promote` is an obvious, valuable hardening.**

> **Interview line:** "Baseline promotion is a release decision, not a build step. Ours is a tracked file, so promotion is a reviewable diff — you can see exactly which numbers moved and who signed off. The gap I'd close is making `--promote` refuse to run on a failing report."

---

## 6. The markdown report

`format_gate_summary` builds a PR-ready document:

```markdown
# Eval Gate Report

**Baseline commit:** e569cfd
**Current commit:** abc1234
**Result:** FAIL

## Failures
- `floor.ragas.anthropic.faithfulness`: faithfulness=0.720 below floor 0.800
- `regression.latency.openai`: p95 latency up 42.3% (3200ms → 4554ms), limit 30.0%

## RAGAS scores
- **anthropic** current: faithfulness=0.720, answer_relevancy=0.840, ...
  baseline: faithfulness=0.850, answer_relevancy=0.850, ...

## Warnings
- Skipping floor check: ragas.openai.answer_correctness (missing data)
```

Design points:

- **Both commits at the top** — reproducibility. You can `git diff e569cfd..abc1234` immediately.
- **Failures before scores** — the reader needs the verdict first.
- **Current *and* baseline side by side** — context without a second lookup.
- **Warnings last** — present but not shouting.
- Conditional sections (`if deepeval:`, `if promptfoo:`) keep it short when those didn't run.

Built as `lines: list[str]` then `"\n".join(lines)` — O(n) rather than repeated string concatenation.

---

## 7. Testing the gate

`tests/test_gate.py` — five tests, no API keys, milliseconds:

| Test | Asserts |
|---|---|
| `test_gate_passes_when_metrics_stable` | Small drops (≤0.02) and small latency increases pass |
| `test_gate_fails_on_large_faithfulness_drop` | 0.90 → 0.80 with `max_metric_drop=0.05` fails |
| `test_gate_fails_on_latency_regression` | 2000ms → 3000ms (50%) with limit 0.30 fails |
| `test_gate_fails_on_promptfoo_pass_rate_regression` | 0.90 → 0.80 fails |
| `test_gate_fails_on_deepeval_floor_breach` | `citation_correctness` 0.65 vs floor 0.70 fails |

Each asserts both `result.passed` **and** that the right failure was recorded:

```python
assert not result.passed
assert any("faithfulness" in f.check for f in result.failures)
```

**Checking the failure identity, not just the boolean, is what makes these tests meaningful.** A gate that fails for the wrong reason is still broken.

Note the tests pass tolerances explicitly (`max_metric_drop=0.05`) rather than relying on `thresholds.yaml`. That decouples the tests from config changes — tuning a threshold shouldn't break the gate's unit tests. Deliberate and correct.

> **Interview line:** "We test the gate with synthetic reports. Five tests, no API keys, sub-second. If you can't test your quality gate cheaply, you'll never refactor it, and it'll rot."

---

## 8. CI — cost-tiered

`.github/workflows/eval-gate.yml`. The policy is stated in a comment at the top:

```yaml
# CI cost policy:
#   PR / push → unit only (free) + eval-fast (API tests skipped unless secrets set)
#   workflow_dispatch → optional full eval (RAGAS, DeepEval, gate, promote)
```

### The three jobs

| Job | Trigger | Timeout | Cost | Runs |
|---|---|---|---|---|
| `unit` | PR + push | 5 min | $0 | `make unit` — no API keys |
| `eval-fast` | PR + push (`needs: unit`) | 20 min | ~$0–0.30 | adversarial + budget + gate (advisory) |
| `eval-full` | `workflow_dispatch` only | 45 min | ~$1.50–2.50 | everything + gate (blocking) + optional promote |

**`needs: unit`** — don't spend money if the free tests already fail. That dependency is the cheapest cost optimization in CI.

**Timeouts on every job** — a hung LLM call would otherwise burn runner minutes indefinitely.

**`eval-full` on `workflow_dispatch` only** — the expensive suite never runs automatically. That's a deliberate cost/coverage tradeoff and you should be able to state its downside: **regressions only detectable by the full suite are found late**, at manual-run time rather than at PR time. A larger team might run `eval-full` nightly on `main` as the compromise.

### Environment strategy

```yaml
env:
  EMBEDDING_PROVIDER: local     # no OpenAI key needed for ingestion
  EVAL_PROVIDERS: anthropic     # halve the API bill
  EVAL_USE_CACHE: "1"           # reuse agent trajectories
```

Three cost decisions in three lines, all enabled by design choices made elsewhere: the embedding abstraction ([`02`](02_INGESTION_AND_EMBEDDINGS.md)), the provider skip logic and the trajectory cache ([`07`](07_EVAL_HARNESS.md)).

### Caching

```yaml
- uses: actions/cache@v4
  with:
    path: chroma_db
    key: chroma-${{ hashFiles('corpus/eu_ai_act.pdf') }}
```

Keyed on the **PDF hash**, so the index is rebuilt only when the corpus changes. `eval-full` extends this to `.eval_cache` keyed on `hashFiles('corpus/eu_ai_act.pdf', 'eval/datasets/golden.jsonl')` — dataset changes invalidate cached trajectories.

⚠️ Same gap as noted in [`07`](07_EVAL_HARNESS.md): the key doesn't include the model name, so a model version bump reuses stale trajectories.

### Conditional ingestion

```bash
if [ ! -d chroma_db ] || [ "$(find chroma_db -type f | wc -l)" -eq 0 ]; then
  if [ -f corpus/eu_ai_act.pdf ]; then
    python scripts/ingest_corpus.py
  else
    echo "SKIP: corpus/eu_ai_act.pdf not in repo"
  fi
fi
```

Handles both "cache hit, skip ingest" and "PDF not committed (it isn't — `.gitignore`), skip gracefully." The `find | wc -l` check catches a restored-but-empty cache directory, which a bare `-d` test would miss.

### Artifacts

```yaml
- name: Upload eval report
  if: always()
  uses: actions/upload-artifact@v4
  with: {name: eval-report-fast, path: eval/reports/}
```

**`if: always()`** — upload even when the job failed. The report is *most* valuable on failure. Forgetting this is a common CI mistake.

### Secrets

```yaml
env:
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

If unset, they're empty strings → `anthropic_configured()` returns `False` → `pytest_collection_modifyitems` skips API tests → **the job still passes on unit coverage.** Forks and external contributors get a meaningful green build without repo secrets. That's a real design achievement, not an accident.

---

## 9. The calibration workflow

```bash
make eval-full           # on main, with a good corpus and both keys
# inspect eval/reports/current.json — are the numbers sensible?
# tune eval/thresholds.yaml if floors are mis-set
make promote-baseline    # commit baseline.json as a reviewed change
```

`make calibrate` just prints these instructions — a documentation target, which is a nice pattern for encoding a procedure where people will find it.

### How to actually set thresholds

1. Run `eval-full` **five times unchanged**. Record each metric's values.
2. Compute mean and standard deviation per metric. **That's your noise floor.**
3. Set `max_metric_drop` above the observed noise (5pp is a reasonable default if σ ≈ 1–2pp).
4. Set absolute floors below your current mean but above your acceptable minimum.
5. Re-check quarterly, and after any model version change.

**Thresholds set without measuring variance are guesses**, and they produce either a flaky gate (too tight) or a useless one (too loose). Being able to describe this procedure is a strong senior signal.

---

## 10. The five-failure drill

Run this. It's the single best hour in the curriculum.

Edit `eval/reports/current.json` by hand and run `make gate` after each:

| # | Edit | Expected failure |
|---|---|---|
| 1 | `ragas.anthropic.faithfulness` → `0.70` | `floor.ragas.anthropic.faithfulness` |
| 2 | `ragas.anthropic.answer_relevancy` → `0.79` (baseline 0.85) | `regression.ragas.anthropic.answer_relevancy` |
| 3 | `latency_p95_ms.anthropic` → `5000` (baseline 3500) | `regression.latency.anthropic` + latency floor |
| 4 | `adversarial.rag_passed` → `false` | `adversarial.rag_passed` |
| 5 | Delete `ragas.anthropic.faithfulness` entirely | **warning, not failure** ← the important one |

Case 5 is the lesson. Read the summary, then write down your argument for whether that default is correct.

---

## Exercises

1. Run the five-failure drill. Save each `gate-summary.md`.
2. Add a `required_metrics` list to `thresholds.yaml` and make the gate fail (not warn) when a required metric is absent from `current.json`. Add a unit test.
3. Make `--promote` refuse to run when `compare_reports` fails, with a `--force` escape hatch. Test both paths.
4. Derive `GateResult.passed` from `len(failures) == 0` instead of setting it imperatively. Does anything break?
5. Add a `--json` output mode for dashboard consumption.
6. Add a nightly `schedule:` trigger running `eval-full` on `main`. What's the monthly cost? Is it worth it?
7. Add a step that posts `gate-summary.md` as a PR comment.
8. Add the model name to the CI cache key so a model bump invalidates trajectories.

## Interview questions this section answers

- "How do you prevent quality regressions in an LLM system?" *(floors + regression + latency + adversarial ratchet)*
- "Why both absolute floors and relative regression checks?"
- "How do you set your thresholds?" *(measure variance across repeated runs)*
- "How do you handle CI cost for LLM evals?" *(three tiers, provider restriction, caching, manual full runs — and the tradeoff)*
- "What happens when a metric goes missing from your report?" *(warning today — and here's why I'd change it)*
- "How do you decide when to update the baseline?" *(reviewed commit, green full run, deliberate release decision)*
- "How do you test the thing that tests your tests?"
