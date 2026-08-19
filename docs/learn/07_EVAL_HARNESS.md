# 07 — The Eval Harness

Files: `eval/reporting.py`, `eval/conftest.py`, `eval/helpers.py`, `eval/metrics_registry.py`, `eval/thresholds.yaml`, `eval/datasets/golden.jsonl`, `eval/agent/golden_trajectories.jsonl`, `conftest.py`

This is the infrastructure that makes measurement repeatable, cheap, and comparable. It is the part of the repo that most directly maps to "AI QA engineer" as a job.

---

## 1. The central architectural idea: measure ≠ gate

`eval/reporting.py`'s docstring states it:

> *"separating **measurement** (tests) from **gating** (eval/gate.py) mirrors how production teams run eval harnesses and compare artifacts in CI."*

```
pytest suites          →  ReportCollector  →  eval/reports/current.json
                                                      │
eval/reports/baseline.json ──────────────┐            │
eval/thresholds.yaml ────────────────────┼────────► eval/gate.py ──► exit 0 / 1
                                         │                          + gate-summary.md
```

### Why the separation matters

| Coupled (tests assert + block) | Decoupled (this repo) |
|---|---|
| Re-running the gate means re-running $$$ evals | Gate runs offline on JSON, instantly, free |
| No historical artifact | Every run produces a comparable artifact |
| Can't change tolerance without changing tests | Tolerance lives in `thresholds.yaml` |
| Can't compare across commits | `current.json` vs `baseline.json` is a diff |
| Gate logic is untestable | `tests/test_gate.py` tests it with fixtures, no API |

Note that tests *also* assert individually (`assert value >= floor`), so a failing metric fails its own test AND lands in the report. Belt and braces: the test failure gives you a precise stack trace and the report gives you the aggregate view.

> **Interview line:** "Our tests measure and record; a separate gate decides. That means the gate is a pure function over two JSON artifacts — which makes it unit-testable, re-runnable for free, and independently tunable."

---

## 2. `ReportCollector`

```python
class ReportCollector:
    _data: dict[str, Any] = {}

    @classmethod
    def reset(cls) -> None:
        cls._data = {
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "commit": _git_commit(),
            "ragas": {}, "latency_p95_ms": {}, "cost_per_query_usd": {},
            "adversarial": {"rag_passed": None, "agent_passed": None},
            "agent": {"cases_run": 0}, "deepeval": {}, "promptfoo": {},
        }

    @classmethod
    def set(cls, path: str, value: Any) -> None:
        parts = path.split(".")
        node = cls._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
```

### Class-level mutable state as a session singleton

`_data` is a class attribute, not an instance attribute. Every `ReportCollector.set(...)` from any test module writes to the same dict — no instance passing, no fixture threading through 12 files.

The cost: it's global mutable state, which is why `reset()` exists and why `pytest_configure` calls it. Without the reset, a second pytest run in the same process would accumulate stale metrics.

An alternative design would be a session-scoped pytest fixture. Class state was chosen because tests call it from module-level helper functions where a fixture isn't in scope. Know both, be able to argue either.

### Dotted-path setter

```python
ReportCollector.set("ragas.anthropic.faithfulness", 0.87)
```

`setdefault` walks/creates the intermediate dicts. This gives call sites a flat, readable API over a nested structure — and it means metric names can be composed with f-strings:

```python
ReportCollector.set(f"ragas.{provider}.{metric}", value)
ReportCollector.set(f"deepeval.{provider}.{metric_name}", mean_score(scores))
ReportCollector.set(f"latency_p95_ms.{provider}", p95)
```

Note there's a matching `increment()` for counters (used for `agent.cases_run`), same walking logic.

### The report schema

```json
{
  "version": 1,
  "commit": "e569cfd",
  "timestamp": "2026-06-17T16:45:00+00:00",
  "ragas":              {"anthropic": {...}, "openai": {...}},
  "latency_p95_ms":     {"anthropic": 3500, "openai": 3200},
  "cost_per_query_usd": {"anthropic": 0.004, "openai": 0.002},
  "adversarial":        {"rag_passed": true, "agent_passed": true},
  "agent":              {"cases_run": 12},
  "deepeval":           {"anthropic": {...}, "openai": {...}, "trajectory_quality": 0.75},
  "promptfoo":          {}
}
```

Three fields that make this a proper artifact:

- **`version: 1`** — schema versioning. When you add a field, older baselines still parse; when you make a breaking change, you can branch on version.
- **`commit`** — via `git rev-parse --short HEAD`, wrapped in try/except returning `"unknown"`. This is what makes `gate-summary.md` able to say "baseline commit e569cfd → current commit abc1234". **Without it, a regression report is unactionable.**
- **`timestamp`** — set at reset *and* again at save, so it reflects run completion.

Note the `deepeval` block mixes shapes: `deepeval.anthropic.faithfulness` (per-provider) and `deepeval.trajectory_quality` (agent, provider-agnostic). The gate handles both with separate loops — `DEEPEVAL_PROVIDER_METRICS` vs `DEEPEVAL_AGENT_METRICS`. Slightly awkward schema; know why it is that way (agent runs are Anthropic-only).

---

## 3. pytest hooks — `eval/conftest.py`

Three hooks, each doing real work.

### `pytest_configure` — session setup

```python
def pytest_configure(config):
    from dotenv import load_dotenv
    load_dotenv()
    deepeval_key = Path(".deepeval")
    if deepeval_key.is_dir():
        import shutil
        shutil.rmtree(deepeval_key)
    ReportCollector.reset()
```

- Load `.env` **before** any test module imports a provider.
- Clean up a DeepEval quirk (it expects `.deepeval` to be a key *file*; some versions leave a directory). This is a workaround with a comment — exactly how third-party quirks should be handled.
- Reset the collector.

### `pytest_collection_modifyitems` — dynamic skipping

This is the most useful hook to know, and the trickiest.

```python
def pytest_collection_modifyitems(config, items):
    if os.getenv("EVAL_SKIP_API") == "1":
        skip = pytest.mark.skip(reason="EVAL_SKIP_API=1")
        for item in items:
            if "eval" in item.keywords or "adversarial" in item.keywords:
                item.add_marker(skip)
        return

    allowed = _eval_providers()      # EVAL_PROVIDERS env, default "anthropic,openai"
    from app.env_check import anthropic_configured, openai_configured
    if not anthropic_configured() and not openai_configured():
        ... skip all eval/adversarial ...
        return

    for item in items:
        if not (hasattr(item, "callspec") and item.callspec and "provider" in item.callspec.params):
            continue
        provider = item.callspec.params["provider"]
        if provider not in allowed:
            item.add_marker(pytest.mark.skip(reason=f"provider {provider} not in EVAL_PROVIDERS"))
        elif not _provider_api_ready(provider):
            item.add_marker(pytest.mark.skip(reason=f"{provider} API key not configured"))
```

**The key mechanism:** `item.callspec.params` exposes the *parametrized values* for a collected test. Because every eval test uses `@pytest.mark.parametrize("provider", [...])`, this hook can inspect which provider each individual test case will use and skip it selectively.

Three levels of control, in order:

1. `EVAL_SKIP_API=1` — nuclear off switch, skip everything needing a network call.
2. No keys at all — skip everything `eval`/`adversarial`.
3. Per-provider — skip only the cases for providers you lack a key for, or that `EVAL_PROVIDERS` excludes.

**This is what makes the same test suite work in three environments:**

| Environment | Behavior |
|---|---|
| Local, both keys | Everything runs |
| Local, Anthropic only | OpenAI cases skip with a clear reason |
| CI PR, no secrets | Eval/adversarial skip; unit tests still run and gate the merge |

The CI workflow sets `EVAL_PROVIDERS: anthropic` explicitly — **halving the API bill** while keeping full coverage of the Anthropic path.

> **Interview line:** "Our eval suite adapts to the environment rather than failing in it. A contributor with one API key gets a green, meaningful run; CI runs one provider to halve cost; the skip reasons say exactly why anything was skipped."

⚠️ The one weakness: skips are silent-ish. A CI run where *everything* skipped is green but measured nothing. A hardening step is to assert a minimum number of executed eval tests, or to check the report has metrics. `pytest_sessionfinish` partially covers this — see next.

### `pytest_sessionfinish` — conditional save

```python
def pytest_sessionfinish(session, exitstatus):
    if session.config.getoption("--collect-only", default=False):
        return
    data = ReportCollector.data()
    has_metrics = bool(data.get("ragas") or data.get("latency_p95_ms")
                       or data.get("deepeval") or data.get("promptfoo"))
    has_adversarial = (data.get("adversarial") or {}).get("rag_passed") is not None
    if has_metrics or has_adversarial:
        ReportCollector.save()
```

**Only write `current.json` if something was actually measured.** Critical: if every eval test skipped (no keys), writing an empty report would make the gate compare a valid baseline against an empty current, generating a wall of "missing data" warnings — or worse, appearing to pass.

`--collect-only` guard prevents a discovery run from clobbering a real report.

---

## 4. Trajectory caching — CI cost control

```python
CACHE_DIR = Path(".eval_cache/agent")
USE_CACHE = os.getenv("EVAL_USE_CACHE", "1") != "0"

def _cache_key(question: str, case_id: str = "") -> str:
    raw = f"{case_id}:{question}" if case_id else question
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def load_cached_agent_run(question, cache_dir, *, case_id=""):
    from app.agent.runner import AgentRun, TrajectoryStep
    path = cache_dir / f"{_cache_key(question, case_id)}.json"
    if not USE_CACHE or not path.exists():
        return None
    data = json.loads(path.read_text())
    return AgentRun(
        question=data["question"], final_answer=data["final_answer"],
        trajectory=[TrajectoryStep(**s) for s in data["trajectory"]],
        steps_taken=data["steps_taken"], stopped_reason=data["stopped_reason"],
        input_tokens=data["input_tokens"], output_tokens=data["output_tokens"],
    )

def save_cached_agent_run(run, cache_dir, *, case_id=""):
    from dataclasses import asdict
    path = cache_dir / f"{_cache_key(run.question, case_id)}.json"
    path.write_text(json.dumps(asdict(run), indent=2))
```

### The economics

Three test files consume agent runs for the same golden cases:

- `eval/agent/test_tool_selection.py` — 3 tests × 12 cases
- `eval/agent/test_deepeval_agent.py` — `tool_correctness` + `task_completion` over the same cases
- (plus trajectory judge on its own question set)

Without caching, each of those triggers a fresh multi-step agent run: 12 cases × ~5 tests × ~4 steps × ~1500 tokens. **With caching, it's 12 agent runs total.** The docstring calls it out:

> *"caching trajectories teaches CI cost control. One agent run per golden case, shared across tool-selection / content / loop tests."*

The `.eval_cache/agent/` directory in the repo contains 12 files — one per golden case. That's the cache working.

### Content-addressed keys

`sha256(f"{case_id}:{question}")[:16]` — deterministic, filesystem-safe, collision-resistant enough at 64 bits for this scale. Change the question text and you get a different key, so stale entries are naturally orphaned rather than silently reused.

Including `case_id` means two golden cases with identical question text still get separate entries.

### The correctness tradeoff — say this out loud

**A cached trajectory is a frozen sample of a non-deterministic process.** Consequences:

- ✅ Runs are fast, cheap, and reproducible — you can iterate on *assertions* without re-paying for *runs*.
- ❌ You are no longer testing the current model's behavior. A model version change won't be caught until the cache is cleared.
- ❌ Non-determinism is hidden. A prompt that succeeds 60% of the time looks 100% reliable if you cached a success.

Mitigations present: `EVAL_USE_CACHE=0` forces fresh runs; CI keys the cache on `hashFiles('corpus/eu_ai_act.pdf', 'eval/datasets/golden.jsonl')` so dataset changes invalidate it.

Mitigation *missing*, and worth proposing: the cache key doesn't include the **model name** or the **agent system prompt hash**. Bump `ANTHROPIC_MODEL` and you'd keep serving old trajectories. Adding those to the key is a small, high-value fix.

> **Interview framing:** "Caching non-deterministic runs is a cost/fidelity tradeoff. We cache by default for iteration speed and clear on dataset change; the honest gap is that the key doesn't include the model version, so a model bump can go unnoticed. I'd add it."

---

## 5. Indirect parametrization

```python
@pytest.fixture
def agent_run_for_case(agent_cache_dir, request):
    case = request.param                       # ← the golden case dict
    run = load_cached_agent_run(case["question"], agent_cache_dir, case_id=case.get("id", ""))
    if run is None:
        from app.agent import run_agent
        run = run_agent(case["question"])
        save_cached_agent_run(run, agent_cache_dir, case_id=case.get("id", ""))
    return case, run
```

Used as:

```python
CASES = load_golden_agent()

@pytest.mark.eval
@pytest.mark.parametrize("agent_run_for_case", CASES, indirect=True, ids=lambda c: c["id"])
def test_tool_selection(agent_run_for_case):
    case, run = agent_run_for_case
```

**`indirect=True` is the piece to understand.** Normally `parametrize("x", values)` injects each value as the argument `x`. With `indirect=True`, each value is passed to the *fixture* named `x` via `request.param`, and the test receives the fixture's **return value**.

So the fixture becomes a parametrized factory: "given a golden case dict, give me the (case, run) pair — cached if possible."

`ids=lambda c: c["id"]` makes test output read `test_tool_selection[agent-001]` instead of `test_tool_selection[case3]`. Essential for debugging.

Three separate test functions use this fixture with the same `CASES` list. Within one pytest session the fixture is function-scoped so it re-executes — but `load_cached_agent_run` hits the on-disk cache, so no extra API calls.

---

## 6. Golden datasets as contracts

### RAG goldens — `eval/datasets/golden.jsonl` (23 cases)

```json
{"id": "rag-001",
 "question": "What is the definition of an AI system under the EU AI Act?",
 "expected_answer": "An AI system is a machine-based system designed to operate with varying levels of autonomy...",
 "tags": ["definitions", "article-3"],
 "must_refuse": false}
```

| Field | Consumed by |
|---|---|
| `id` | test ids, cache keys, promptfoo `description` |
| `question` | the input |
| `expected_answer` | RAGAS `ground_truth`, DeepEval `expected_output`, promptfoo `llm-rubric` reference |
| `tags` | `filter_cases_for_geval` — e.g. `citation_correctness` only runs on `article-*` tagged cases |
| `must_refuse` | selects the refusal assertion path in both DeepEval and promptfoo |

**Why JSONL and not JSON/CSV/YAML:** one record per line means clean `git diff` when a case is added or edited, streamable parsing, and no whole-file re-indentation. This matters when the dataset is reviewed in PRs — which it should be.

**`tags` are the routing mechanism.** From `eval/deepeval_helpers.py`:

```python
def filter_cases_for_geval(metric_name, rows):
    if metric_name == "citation_correctness":
        return [r for r in rows if any("article" in t for t in r.tags)]
    if metric_name == "refusal_correctness":
        return [r for r in rows if r.must_refuse or "negative-test" in r.tags]
    return rows
```

**Running every rubric against every case is wasteful and misleading.** Scoring `citation_correctness` on a case with no article reference produces a meaningless number that then drags the mean around. Tag-based filtering is the fix, and it's a strong detail to mention.

### Agent goldens — `eval/agent/golden_trajectories.jsonl` (12 cases)

```json
{"id": "agent-001",
 "question": "What is the maximum fine for using prohibited AI practices?",
 "expected_tools": ["compute_fine"],
 "forbidden_tools": [],
 "expected_in_answer": ["35", "million", "7%"],
 "tags": ["fine-lookup"]}
```

Assertion vocabulary:

| Field | Semantics |
|---|---|
| `expected_tools` | **all** must appear in the trajectory |
| `expected_tools_any_of` | **any one** of several acceptable sequences (allows legitimate strategy variation) |
| `forbidden_tools` | none may appear |
| `expected_in_answer` | substrings (case-insensitive) that must be present |
| `must_not_contain` | substrings (case-sensitive) that must be absent |

`expected_tools_any_of` is the interesting one — it's the concession to non-determinism. "Is social scoring banned?" can legitimately be answered via `search_ai_act` **or** `lookup_article(5)` **or** `check_risk_tier`. Forcing one would produce a flaky test that punishes correct behavior.

```python
if "expected_tools_any_of" in case:
    ok = any(all(t in called for t in option) for option in case["expected_tools_any_of"])
    ok = ok or [] in case["expected_tools_any_of"]
    assert ok
```

The `[] in ...` clause allows "no tools at all" as an explicitly acceptable option — used for greeting-type cases.

### Growing the dataset

Every production failure should become a golden case. That's the flywheel:

```
incident → reproduce → add golden case → it fails → fix → it passes → gate protects it forever
```

Say this in an interview. It's the single clearest signal that you understand eval datasets as *living regression suites* rather than a one-time benchmark.

---

## 7. Thresholds as data

`eval/thresholds.yaml`:

```yaml
version: 1
ragas:
  faithfulness: 0.80
  answer_relevancy: 0.80
  context_precision: 0.75
  context_recall: 0.75
  answer_correctness: 0.70
  answer_similarity: 0.70
  context_entity_recall: 0.65
  context_relevance: 0.70
deepeval:
  faithfulness: 0.70
  ...
  refusal_correctness: 0.80      # ← highest floor: safety > quality
gate:
  max_metric_drop: 0.05
  max_latency_increase: 0.30
latency:
  max_p95_ms: 4000
cost:
  max_per_query_usd: {anthropic: 0.01, openai: 0.005}
metamorphic:
  paraphrase_similarity: 0.78
bias:
  demographic_similarity: 0.82
```

### Why YAML, not constants in code

- Tuning a threshold is a one-line, reviewable diff — no code change, no logic risk
- Both tests and the gate read the same file, so they cannot disagree
- Non-engineers can review the quality bar
- Diffs in PRs make threshold *relaxation* visible — a threshold quietly dropped from 0.80 to 0.65 is exactly the change that should require justification

### The accessor

```python
def threshold(path: str, default: float) -> float:
    node: object = load_thresholds()
    for part in path.split("."):
        if not isinstance(node, dict):
            return default
        node = node.get(part, default)
    return float(node) if node is not None else default
```

Dotted-path read with a default, mirroring `ReportCollector.set`. Every call site supplies a sensible default, so a missing YAML entry degrades to a hardcoded fallback rather than crashing.

⚠️ `load_thresholds()` re-reads and re-parses the file on **every** call. In `test_deepeval.py`, that's once per metric per provider. Trivially cacheable with `@lru_cache`. Real, small optimization.

### Reading the numbers

The values encode a quality philosophy — be able to defend them:

- **`refusal_correctness: 0.80`** is the highest floor. Refusing correctly is a *safety* property; answering a question you shouldn't is worse than answering imperfectly.
- **`hallucination: 0.50`** looks low until you check DeepEval's semantics for that metric — always verify metric direction before reading a threshold.
- **`context_entity_recall: 0.65`** is lowest among RAGAS. Entity recall is brittle on legal text (entity extraction struggles with "Regulation (EU) 2024/1689").
- **`max_metric_drop: 0.05`** — 5 percentage points. Loose enough to absorb LLM-judge run-to-run variance, tight enough to catch a real regression. **This is the single most important number to be able to justify**, and the honest justification is empirical: measure your own run-to-run variance across ~5 identical runs and set the tolerance above it.
- **`max_latency_increase: 0.30`** — relative, not absolute, so it stays meaningful as the baseline shifts.

---

## 8. The metric registry

`eval/metrics_registry.py` — no logic, just tuples:

```python
RAGAS_METRICS: tuple[str, ...] = ("faithfulness", "answer_relevancy", "context_precision",
    "context_recall", "answer_correctness", "answer_similarity",
    "context_entity_recall", "context_relevance")

DEEPEVAL_RAG_BUILTIN_METRICS = ("faithfulness", "answer_relevancy", "contextual_relevancy",
    "contextual_precision", "contextual_recall", "hallucination")
DEEPEVAL_RAG_GEVAL_METRICS = ("citation_correctness", "refusal_correctness",
    "conciseness", "article_hallucination")
DEEPEVAL_AGENT_METRICS = ("trajectory_quality", "tool_correctness", "task_completion")
DEEPEVAL_PROVIDER_METRICS = (*DEEPEVAL_RAG_BUILTIN_METRICS, *DEEPEVAL_RAG_GEVAL_METRICS)

PROMPTFOO_METRICS = ("pass_rate", "passed", "total", "failed")
PROVIDERS: tuple[str, ...] = ("anthropic", "openai")
```

### The problem it solves

Metric names appear in four places: the test that computes them, the report key, the thresholds file, and the gate's iteration. **Four places to typo.** A typo means the gate silently skips that metric — it becomes a *warning* about missing data, not a failure. A metric you think is gated but isn't is worse than no metric at all.

The registry makes the test and the gate iterate over the *same* tuple:

```python
# eval/test_ragas.py
for metric in RAGAS_METRICS:
    ReportCollector.set(f"ragas.{provider}.{metric}", value)

# eval/gate.py
for metric in RAGAS_METRICS:
    value = (current.get("ragas") or {}).get(provider, {}).get(metric)
```

`thresholds.yaml` is still string-keyed and *not* mechanically checked against the registry — that's the remaining gap. A five-line test asserting every registry metric has a threshold entry would close it. **Propose this; it's a good answer to "what would you improve?"**

`DEEPEVAL_PROVIDER_METRICS` uses tuple unpacking (`*a, *b`) to compose — derive, don't duplicate.

`PROVIDERS` being a tuple (immutable) rather than a list signals "constant" and prevents accidental mutation.

---

## 9. Layered conftest

| File | Scope | Does |
|---|---|---|
| `conftest.py` (root) | everything | `load_dotenv()` — that's all |
| `eval/conftest.py` | `eval/` only | report collection, skip logic, agent cache fixtures |
| (none in `tests/`) | — | unit tests need nothing beyond `.env` |

pytest collects conftests from the rootdir down to the test file, so `eval/` tests get both. `tests/` gets only the root one — **which is the point**: unit tests must not depend on eval infrastructure, and the absence of a `tests/conftest.py` enforces that structurally.

---

## Exercises

1. Delete `.eval_cache/`, time `pytest eval/agent/ -m eval`. Restore, time again. Compute the saving in seconds and (estimated) dollars.
2. Add the model name to `_cache_key`. Verify a model change invalidates the cache. Write a test.
3. Write `tests/test_thresholds_complete.py` asserting every name in `metrics_registry` has an entry in `thresholds.yaml`.
4. Add `@lru_cache` to `load_thresholds`. What's the risk, and how would you make the cache clearable for tests?
5. Add 3 golden cases: one `must_refuse: true`, one tagged `article-*`, one requiring multi-hop reasoning. Run RAGAS and see how the means move.
6. Build a RAG-result cache fixture mirroring `agent_run_for_case`. What's the right cache key?
7. Add an assertion in `pytest_sessionfinish` that fails the session if `eval` tests ran but produced zero metrics.

## Interview questions this section answers

- "How do you structure an eval suite so it's affordable to run?" *(tiering, caching, per-provider skips)*
- "Why separate measuring from gating?"
- "How do you keep an eval suite from becoming flaky?" *(property assertions, tolerances, caching, tuned thresholds)*
- "How do you build and grow a golden dataset?" *(contract fields, tags for routing, incident→case flywheel)*
- "Where do your thresholds come from?" *(measure run-to-run variance, set tolerance above it, YAML so changes are reviewable)*
- "How does your suite behave for a contributor with only one API key?"
