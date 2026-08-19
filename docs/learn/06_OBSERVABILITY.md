# 06 — Observability

File: `app/observability.py` (134 lines), plus `docker-compose.yml`

The module's own docstring states the thesis:

> *"observability is not optional in AI QA. You need traces to debug **why** faithfulness dropped (bad retrieval? prompt drift? model change?)."*

That's the whole argument. Metrics tell you *that* quality dropped. Traces tell you *where*.

---

## 1. The vocabulary

| Term | Meaning here |
|---|---|
| **Trace** | One end-to-end request (a `/query` or an agent run) |
| **Span / Observation** | One timed unit of work within a trace |
| **Observation type** | A semantic label — `generation`, `retriever`, `tool`, `agent`, `chain`, `embedding`, `evaluator`, `guardrail` |
| **Nesting** | Spans form a tree via parent-child context |

The types are declared as a `Literal`:

```python
ObservationType = Literal["span", "generation", "embedding", "agent", "tool",
                          "chain", "retriever", "evaluator", "guardrail"]
```

Typing them means a typo like `as_type="retreiver"` is a mypy error, not a silently mis-categorized span.

### The trace tree this produces

```
answer                          (chain)      ← @observe on app.rag.answer
├─ retrieve                     (retriever)  ← @observe on app.rag.retrieve
│  └─ retrieve.hybrid           (retriever)  ← with trace(...) in pipeline.retrieve_advanced
└─ llm_generate                 (generation) ← with trace(...) in answer_with_chunks

run_agent                       (agent)      ← with trace(...) in runner.run_agent
├─ tool.search_ai_act           (tool)
│  └─ retrieve → retrieve.hybrid             ← the agent inherits RAG's spans
├─ tool.compute_fine            (tool)
└─ tool.lookup_article          (tool)
```

**Every layer is instrumented, and the agent's tool spans nest the RAG spans underneath.** When an agent gives a bad answer you can drill from the agent run → the tool call → the retrieval → the specific chunks returned.

---

## 2. The null-object pattern

```python
_enabled: bool | None = None

def _is_enabled() -> bool:
    global _enabled
    if _enabled is None:
        _enabled = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
    return _enabled

@contextmanager
def trace(name, *, input=None, metadata=None, as_type="span"):
    lf = get_langfuse()
    if lf is None:
        yield None
        return
    ...
```

**When Langfuse isn't configured, `trace` yields `None` and does nothing.** Every call site works unchanged:

```python
with trace("llm_generate", input={...}, as_type="generation"):
    resp = llm.generate(...)
```

No `if OBSERVABILITY_ENABLED:` branches anywhere in the application code. That's the payoff: instrumentation is unconditional at the call site and conditional in exactly one place.

The `@observe` decorator handles the `None` case too:

```python
with trace(trace_name, ...) as obs:
    result = fn(*args, **kwargs)
    if obs is not None:
        obs.update(output=_safe(result))
    return result
```

**Why this matters for testing:** the entire unit suite (`tests/`) runs with no Langfuse keys. If `trace` raised or required a client, every test would need a mock. Instead it's free.

### The tri-state cache

`_enabled` is `None` (unchecked) / `True` / `False`. This is a memoization idiom worth naming — you can't use a plain `False` default because you couldn't distinguish "checked and disabled" from "not yet checked."

The tradeoff: **it's cached for the process lifetime.** Setting `LANGFUSE_PUBLIC_KEY` after the first call has no effect. Fine for an app; a mild annoyance in a test session. `functools.cache` would express the same thing more clearly.

### Lazy singleton client

```python
_langfuse = None

def get_langfuse():
    global _langfuse
    if not _is_enabled():
        return None
    if _langfuse is None:
        from langfuse import Langfuse       # ← import inside the function
        _langfuse = Langfuse(public_key=..., secret_key=..., host=...)
    return _langfuse
```

Same deferred-import trick as `app/retrieval/reranker.py`: `langfuse` is only imported when actually used, so it isn't a startup cost for unit tests.

⚠️ **Not thread-safe.** Two threads hitting `get_langfuse()` simultaneously on a cold cache can both construct a client. Harmless here (Langfuse clients are cheap and the second one is discarded), but know that the correct form uses a lock or module-level initialization. `@lru_cache` — as used in the reranker — would also be safer.

---

## 3. `trace` as a context manager

```python
@contextmanager
def trace(name, *, input=None, metadata=None, as_type="span"):
    lf = get_langfuse()
    if lf is None:
        yield None
        return

    try:
        observation_cm = lf.start_as_current_observation(
            name=name, as_type=as_type, input=input, metadata=metadata or {})
    except Exception:
        yield None                          # Langfuse broken → degrade, don't break the app
        return

    with observation_cm as obs:
        try:
            yield obs
        except Exception as e:
            try:
                obs.update(level="ERROR", status_message=str(e))
            except Exception:
                pass
            raise                           # ← re-raise: observability never swallows errors
```

### `@contextlib.contextmanager` mechanics

The decorator turns a generator into a context manager:
- everything before `yield` = `__enter__`
- the yielded value = the `as` target
- everything after `yield` = `__exit__`
- an exception in the body is **thrown into the generator at the `yield` point**, which is why `try/except` around `yield` works

The two early returns (`yield None; return`) are the "do nothing" paths. A generator-based context manager **must** yield exactly once — returning after the yield satisfies that.

### The three-layer error handling — read carefully

1. **Outer `try`** — if `start_as_current_observation` fails (Langfuse down, SDK version mismatch), yield `None` and continue. The app is not degraded by a monitoring outage.
2. **Inner `except Exception as e`** — record the error on the span, then **`raise`**. The application exception propagates normally.
3. **Nested `try/except: pass`** around `obs.update` — if even recording the error fails, don't mask the original exception with a monitoring exception.

> **Interview line:** "Observability code must never be the reason a request fails. Ours degrades to no-op at three levels, and it re-raises every application exception — a monitoring failure is invisible to the user, and an application failure is never swallowed by monitoring."

The `level="ERROR"` update means failed spans are visually distinct in the Langfuse UI. Filter to errors and you have your failure feed.

---

## 4. `observe` — decorator built on the same primitive

```python
F = TypeVar("F", bound=Callable[..., Any])

def observe(name: str | None = None, as_type: ObservationType = "span") -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        trace_name = name or fn.__name__

        @wraps(fn)
        def wrapper(*args, **kwargs):
            with trace(trace_name, input={"args": _safe(args), "kwargs": _safe(kwargs)},
                       as_type=as_type) as obs:
                result = fn(*args, **kwargs)
                if obs is not None:
                    obs.update(output=_safe(result))
                return result
        return wrapper  # type: ignore[return-value]
    return decorator
```

### Three-level nesting — this is the canonical decorator-factory shape

```
observe(name, as_type)      ← called with config, returns...
  └─ decorator(fn)          ← called with the function, returns...
       └─ wrapper(*a, **kw) ← the replacement function
```

Because `observe` takes arguments, it must be called before being applied: `@observe(name="retrieve", as_type="retriever")`. Contrast `@wraps` in the same file, which is applied directly. If you want a decorator that works both with and without parentheses you need an extra branch — a classic interview question.

### `@wraps(fn)`

Copies `__name__`, `__doc__`, `__module__`, `__qualname__`, `__dict__`, and sets `__wrapped__`. Without it:
- `retrieve.__name__` would be `"wrapper"`
- `help(retrieve)` shows the wrapper's docstring
- pytest's introspection and `inspect.signature` get confused
- **and `trace_name = name or fn.__name__` on a *stacked* decorator would resolve to `"wrapper"`**

That last point is the practical bite. Always use `@wraps`.

### `TypeVar("F", bound=Callable[...])`

Preserves the decorated function's type for the type checker: `observe(...)(f)` has the same type as `f`. The `# type: ignore[return-value]` is there because mypy can't verify that `wrapper` has type `F` — the honest modern alternative is `ParamSpec` + `Concatenate` (PEP 612), which expresses "same params, same return" precisely. Good refactor exercise.

### When to use `trace` vs `observe`

| | Use |
|---|---|
| `@observe` | Whole-function instrumentation where args/return are the interesting payload — `app/rag.py::answer`, `app/rag.py::retrieve` |
| `with trace(...)` | A *portion* of a function, or when you want to control the payload — `retrieve_advanced`'s hybrid block, `answer_with_chunks`'s LLM call, each agent tool call |

`retrieve_advanced` is the clearest example of why both exist: it traces only the retrieval block, with a curated input payload (`queries`, `k`, `candidate_k`, `article_filter`) that's far more useful than a raw dump of the function arguments.

---

## 5. `_safe` — payload hygiene

```python
def _safe(obj: Any, max_len: int = 2000) -> Any:
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    if isinstance(obj, str):
        return obj[:max_len]
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict
        try:
            return asdict(obj)
        except Exception:
            pass
    try:
        return str(obj)[:max_len]
    except Exception:
        return "<unrepr>"
```

Four concerns, all real:

1. **Truncation at 2000 chars.** A `RAGResult` carries 5 chunks × 2000 chars = 10KB. Traced on every call, that's a serious payload and storage bill. Truncate.
2. **Dataclass detection via `__dataclass_fields__`.** The idiomatic check is `dataclasses.is_dataclass(obj)`; `hasattr` avoids the import at module scope. Both work. `asdict` recurses, so `RAGResult` → nested `RetrievedChunk` dicts, which renders as structured JSON in the UI rather than a repr string.
3. **`str()` fallback** for anything else.
4. **`"<unrepr>"`** for objects whose `__str__` itself raises. Rare, but a `__repr__` that throws inside your monitoring layer is a genuinely nasty bug.

⚠️ **Note the asymmetry:** `_safe` truncates strings but `asdict` output is **not** truncated. A dataclass containing long strings serializes in full. Minor, real, and a good "spot the gap" exercise.

---

## 6. `flush` and process lifetime

```python
def flush() -> None:
    lf = get_langfuse()
    if lf is not None:
        lf.flush()
```

Langfuse batches events and sends them on a background thread. In a long-lived server that's invisible. In a short-lived process — pytest, a CLI script, a Lambda — **the process can exit before the batch is sent, and you silently lose traces.**

`run_agent` calls `flush()` after every run. Note that `app/rag.py::answer` does **not** — so RAG traces from a short script may be lost. That's an inconsistency worth noticing and arguably fixing (or better: register `atexit.register(flush)` once).

> **Interview line:** "Batched telemetry plus short-lived processes equals missing data. Anything that runs in CI or a serverless context needs an explicit flush or an atexit hook."

---

## 7. Self-hosting

```yaml
# docker-compose.yml → docker compose up -d → http://localhost:3000
```

Self-hosted Langfuse on port 3000, or Langfuse Cloud via `LANGFUSE_HOST`. Why it matters here: the corpus is public, but a compliance tool in a real deployment would send **customer questions** to a third-party observability vendor. Self-hosting keeps that data in your perimeter. That's a GDPR-relevant answer and a good one to have ready given the domain.

---

## 8. The debugging workflow — practice this

The scenario you will be asked about: *"Faithfulness dropped from 0.85 to 0.71 this week. Go."*

1. **Gate output** (`eval/reports/gate-summary.md`) — which metric, which provider, how much, vs which baseline commit.
2. **Diff the commits** between baseline and current. Prompt change? Chunking change? Model version bump? Dependency upgrade?
3. **Open Langfuse**, filter to the failing time window.
4. **Compare a good trace to a bad trace** at each level:
   - `retrieve.hybrid` — did the *chunks* change? Then it's ingestion or retrieval.
   - `llm_generate` — same chunks, different answer? Then it's the prompt or the model.
   - Token counts — a jump in input tokens means context assembly changed.
   - Latency per span — locates a performance regression.
5. **Reproduce locally** with the exact question from the trace.
6. **Add a golden case** for it, so the regression can never return silently.

Step 6 is the one candidates forget. **Every production incident should end with a new test case.**

### Metric-to-cause table

| Metric that moved | Likely cause | Trace span to inspect |
|---|---|---|
| `context_precision` ↓ | chunking, reranker, `candidate_multiplier` | `retrieve.hybrid` |
| `context_recall` ↓ | `k` too low, embedding model, BM25 index missing | `retrieve.hybrid` |
| `faithfulness` ↓ | prompt change, model version, temperature | `llm_generate` |
| `answer_relevancy` ↓ | prompt change, over-refusal | `llm_generate` |
| `latency p95` ↑ | reranker load, candidate count, provider | span durations |
| `cost` ↑ | context size, `k`, agent step count | token fields |
| agent `tool_correctness` ↓ | tool descriptions, model version | `tool.*` spans |

---

## Exercises

1. `docker compose up -d`, set `LANGFUSE_*` in `.env`, run 5 RAG queries and 2 agent runs. Find the trace tree. Confirm it matches the diagram in §1.
2. Deliberately degrade retrieval (set `k=1`), run a golden question, and diff the good vs bad trace. Write down exactly which span revealed the cause.
3. Add `@observe` to `app.retrieval.pipeline.retrieve_advanced` *in addition to* the inner `with trace(...)`. What does the tree look like? Is the duplication useful or noise?
4. Add an `atexit.register(flush)` and verify RAG traces survive a short script.
5. Make `_safe` truncate strings nested inside `asdict` output. Write a test.
6. Replace the `TypeVar` in `observe` with `ParamSpec`/`Concatenate` and run mypy. Did the `# type: ignore` become unnecessary?
7. Add a `trace` around the cross-encoder rerank call with the candidate count as metadata. Now you can see reranking latency separately.

## Interview questions this section answers

- "How do you debug a quality regression in a RAG system?" *(the 6-step workflow + the cause table)*
- "What do you instrument, and at what granularity?"
- "How do you make sure observability never breaks the app?" *(three-layer degradation, always re-raise)*
- "Your traces aren't showing up in CI. Why?" *(batching + process exit → flush)*
- "What are the privacy implications of LLM observability?" *(self-hosting, PII in prompts)*
