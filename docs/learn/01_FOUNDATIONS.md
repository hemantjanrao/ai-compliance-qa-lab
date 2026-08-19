# 01 — Application Foundations

Files: `pyproject.toml`, `Makefile`, `app/env_check.py`, `app/providers.py`, `app/guards.py`, `app/retrieval/config.py`, `app/main.py`, `conftest.py`

---

## 1. Packaging and the dependency contract

### What the code does

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*", "eval*"]
```

No `src/` layout. `app` and `eval` are both installable packages, which is why `from eval.gate import compare_reports` works in `tests/test_gate.py` and why `python -m eval.gate` works from the Makefile.

`make setup` runs `pip install -e ".[dev]"` — **editable install**. The package metadata is registered but imports resolve to your working tree, so edits take effect without reinstalling. The `ai_compliance_qa_lab.egg-info/` directory is the artifact of that.

### The concept: pinning as a supply-chain control

```toml
# Pin langchain 0.3.x — ragas 0.4+ breaks on langchain-community 0.4 (vertexai removed)
"langchain>=0.3,<0.4",
"langchain-community>=0.3.20,<0.4",
```

This is **OWASP LLM03 (supply chain)** made concrete. The AI/ML dependency graph moves fast and breaks compatibility across minor versions. Three defenses are in play:

1. **Upper bounds** on packages with known breakage.
2. **A comment explaining why** — otherwise a future maintainer "cleans up" the pin.
3. **A test that asserts the pin exists** — `tests/test_supply_chain.py`:

```python
def test_langchain_and_ragas_pinned_in_pyproject():
    text = Path("pyproject.toml").read_text()
    assert "langchain>=0.3,<0.4" in text
```

That test is unusual and worth understanding. It doesn't test behavior; it tests a **policy**. If someone relaxes the pin, CI fails and forces a conversation. This is the same class as a lint rule, but expressed where the team already looks.

> **Interview framing:** "We treat dependency constraints as testable policy. A pin without a test is a suggestion."



### Optional-dependency groups

```toml
[project.optional-dependencies]
dev = ["pytest", "deepeval", "ragas", "ruff", "mypy", "playwright", ...]
```

Runtime deps and eval deps are separate. A production deployment installs `pip install .` and never pulls `ragas`/`deepeval`. Only CI and local dev install `[dev]`. This keeps the production attack surface and image size down.

### pytest config lives here too

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests", "eval"]
markers = ["eval: ...", "adversarial: ...", "slow: ..."]
```

Three markers give you the cost tiers:


| Marker        | Means                                  | Cost          |
| ------------- | -------------------------------------- | ------------- |
| (none)        | pure unit, no network                  | $0            |
| `adversarial` | red-team, needs API                    | cents         |
| `eval`        | measurement, needs API                 | cents–dollars |
| `slow`        | RAGAS/DeepEval/promptfoo, LLM-as-judge | dollars       |


Declaring markers in config (rather than letting them be implicit) makes `pytest --strict-markers` viable and makes typos fail loudly.

---



## 2. The Makefile as the single interface

```makefile
ifneq ($(wildcard .venv/bin/python),)
  PY := .venv/bin/python
else
  PY := python3
endif
```

Local dev has `.venv`; CI installs into the runner's Python. This conditional means the *same* `make unit` works in both places — no "works on my machine" divergence between the README and the workflow file.

Note the ordering of eval targets:

```makefile
eval-fast:
	$(PY) -m pytest tests/ eval/test_adversarial.py eval/agent/test_adversarial.py eval/test_budget.py -v -m "not slow" --tb=short
	$(PY) -m eval.gate --markdown eval/reports/gate-summary.md || true
```

The `|| true` on `eval-fast` is deliberate: a fast run doesn't produce enough metrics for a meaningful gate verdict, so the gate is informational there. `make eval` and `make eval-full` drop the `|| true` — the gate is authoritative once the full suite has run.

> **Interview framing:** "We tier CI by cost. The gate is advisory on cheap runs and blocking on full runs, because gating on partial data produces noise, and noisy gates get ignored."

---



## 3. Configuration by environment, validated at read time

`app/retrieval/config.py`:

```python
class RetrievalMode(str, Enum):
    BASIC = "basic"
    ADVANCED = "advanced"

def get_retrieval_mode() -> RetrievalMode:
    raw = os.getenv("RAG_RETRIEVAL_MODE", "advanced").lower()
    if raw not in ("basic", "advanced"):
        raise ValueError(f"RAG_RETRIEVAL_MODE must be 'basic' or 'advanced', got: {raw!r}")
    return RetrievalMode(raw)
```

Three things to internalize:

**a)** `str, Enum` **mixin.** `RetrievalMode.BASIC` *is* a `str`, so it serializes to JSON, works in f-strings, and Pydantic accepts it directly as a field type (see `QueryIn.retrieval_mode` in `app/main.py`). Without the `str` mixin you'd need custom encoders.

**b) Function, not module constant.** `get_retrieval_mode()` reads `os.getenv` on every call. A module-level `RETRIEVAL_MODE = os.getenv(...)` would freeze at import time — which breaks tests using `monkeypatch.setenv` and breaks the Streamlit sidebar's ability to switch modes mid-session.

**c) Fail fast with the bad value echoed.** `{raw!r}` uses `repr`, so `'Advanced '` (trailing space) is visible. `!s` would hide it. Small habit, large debugging payoff.

The same pattern repeats in `app/embeddings.py` (`get_embedding_provider`) and `app/guards.py` (`MAX_QUESTION_CHARS`).

⚠️ One inconsistency worth noticing: `MAX_QUESTION_CHARS` in `app/guards.py` *is* a module constant read at import time. That's a deliberate tradeoff (it's used as a default in a signature and in tests) but it means changing the env var mid-process has no effect. Know the difference and be able to defend either choice.

---



## 4. Provider abstraction — the ABC

`app/providers.py` is the cleanest teaching example in the repo.

```python
class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system: str, user: str, max_tokens: int = 1024) -> LLMResponse: ...
```



### Why an ABC and not just duck typing

- `ABC` + `@abstractmethod` makes instantiation of an incomplete subclass fail at construction, not at first call.
- It documents the contract in one place.
- `get_provider()` returns `LLMProvider`, so every call site is typed against the interface, not the vendor.

The payoff is visible everywhere: `answer(question, provider="openai")` vs `provider="anthropic"` changes one string. Every eval test parametrizes over both providers with zero branching:

```python
@pytest.mark.parametrize("provider", ["anthropic", "openai"])
```



### Normalizing vendor responses

The two implementations differ in exactly the ways vendors differ:


|                 | Anthropic                              | OpenAI                                      |
| --------------- | -------------------------------------- | ------------------------------------------- |
| System prompt   | top-level `system=` param              | a `{"role": "system"}` message              |
| Text extraction | `resp.content[0].text`                 | `resp.choices[0].message.content`           |
| Token usage     | `usage.input_tokens` / `output_tokens` | `usage.prompt_tokens` / `completion_tokens` |
| Empty output    | raises/returns block                   | can be `None` → `or ""`                     |


Both collapse into one `LLMResponse` dataclass:

```python
@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: ProviderName
```

**This is the adapter pattern.** The value isn't abstraction for its own sake — it's that `eval/test_budget.py` can compute cost per query with provider-specific rates against a uniform token interface:

```python
cost = (r.input_tokens / 1_000_000) * 1.0 + (r.output_tokens / 1_000_000) * 5.0
```



### `ProviderName = Literal["anthropic", "openai"]`

Not `str`. `Literal` gives you:

- mypy errors on `get_provider("antropic")` (typo) at check time
- Pydantic validation on the API boundary — `QueryIn.provider` rejects anything else with a 422
- autocomplete in editors

The `ValueError` in `get_provider` is the runtime backstop for callers that bypass typing.

---



## 5. Retry policy — the part most people get wrong

```python
def _is_retryable(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "insufficient_quota" in msg or "exceeded your current quota" in msg:
        return False
    if "invalid x-api-key" in msg or "authentication" in msg.lower():
        return False
    return True

_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=30),
    retry=retry_if_exception(_is_retryable),
)
```



### The concepts

**Exponential backoff.** `wait_exponential(min=2, max=30)` waits ~2s, ~4s, ~8s… capped at 30s. The cap matters: unbounded exponential backoff on a 3-attempt policy is fine, but on a 10-attempt policy you'd wait 17 minutes.

**Selective retryability is the real lesson.** Retrying is only correct for *transient* failures. Retrying an auth failure:

- wastes 3× the wall-clock time before surfacing the real error
- muddies the error message (you get `RetryError` wrapping the original)
- in rate-limited systems, contributes to the very congestion you're backing off from

Both excluded classes here are **permanent** within the process lifetime: a bad key stays bad; an exhausted quota stays exhausted.

**Why string matching?** Because the two SDKs raise different exception classes for the same condition, and OpenAI notably returns HTTP 429 for *both* rate-limiting (transient) and quota exhaustion (permanent). Matching on message content is the pragmatic discriminator. It's fragile — a vendor wording change silently degrades it. A hardening exercise: assert on the vendor's structured error `code` field where available, and add a test that pins the current behavior.

**Decorator applied to the method:**

```python
@_retry
def generate(self, system: str, user: str, max_tokens: int = 1024) -> LLMResponse:
```

`_retry` is a *configured decorator object* built once at module level and reused by both classes. This is a decorator factory result — see `[11_ADVANCED_PYTHON.md](11_ADVANCED_PYTHON.md)` §3.

---



## 6. Turning exceptions into UX

`app/env_check.py::format_api_error` is the counterpart to the retry logic.

```python
def format_api_error(exc: BaseException) -> str:
    from tenacity import RetryError
    if isinstance(exc, RetryError):
        if exc.last_attempt and exc.last_attempt.exception():
            exc = exc.last_attempt.exception()
```

**Unwrapping first.** After `_retry` gives up, the caller sees `RetryError`, not the useful underlying exception. Line 1 of the handler is to dig it out. If you skip this, every failure reads "RetryError" and nobody can debug anything.

**Ordering matters:**

```python
# Check quota before generic rate-limit (OpenAI returns 429 for both)
if "insufficient_quota" in msg.lower() or ...:
```

The comment tells you the bug that was fixed. Quota is a subset of 429; check the specific case before the general one. This is the same ordering discipline as exception `except` clauses (subclass before superclass).

**Actionable, not descriptive.** Each branch returns a markdown message with a link and a concrete next step ("add billing at…", "or add an Anthropic key and switch provider in the sidebar"). `app/streamlit_ui.py` renders it directly:

```python
except Exception as e:
    st.error(format_api_error(e))
```

> **Interview framing:** "Error handling has two audiences — the retry policy decides what the *machine* does; the formatter decides what the *human* does. Conflating them gives you either silent retries of permanent failures or stack traces in the UI."

Tested in `tests/test_env_check.py` with locally-defined dummy exception classes — no vendor SDK needed, no network. Note how they name the local classes `RateLimitError`/`AuthenticationError` so the `type(exc).__name__` branch is exercised.

---



## 7. Input guards — OWASP LLM05

```python
MAX_QUESTION_CHARS = int(os.getenv("MAX_QUESTION_CHARS", "4000"))

def validate_question(question: str) -> str:
    q = question.strip()
    if not q:
        raise ValueError("Question must not be empty.")
    if len(q) > MAX_QUESTION_CHARS:
        raise ValueError(f"Question exceeds maximum length ({MAX_QUESTION_CHARS} characters).")
    return q
```

17 lines, three properties worth naming:

1. **It returns the normalized value.** `validate_question` is a *parser*, not a *checker* — it strips and hands back the cleaned string. Callers use the return value (`question = validate_question(question)` in `app/rag.py` and `app/agent/runner.py`). This is the "parse, don't validate" principle: the type system can't express "non-empty stripped string", but funneling through one function that returns the cleaned value gets you most of the benefit.
2. **It's enforced at every entry point**, not just the HTTP boundary:
  - `app/main.py` — Pydantic `field_validator` on both `QueryIn` and `AgentIn`
  - `app/rag.py::answer` — direct call
  - `app/agent/runner.py::run_agent` — direct call
   Defense in depth. A future caller who imports `answer()` directly still gets the guard.
3. **Why it's a security control.** Oversized prompts are a denial-of-wallet attack: token cost is roughly linear in input length, and there's no rate limit on your own code path. 4,000 chars ≈ 1,000 tokens is a sane ceiling for a Q&A app.

Tested at both levels — `tests/test_input_guards.py` covers the function *and* asserts `answer()` propagates it; `tests/e2e/test_api_smoke.py` asserts the HTTP layer returns **422** (Pydantic validation error), not 500.

---



## 8. The API surface

`app/main.py` is small but demonstrates several things precisely.

### Pydantic v2 validators

```python
class QueryIn(BaseModel):
    question: str
    provider: ProviderName = "anthropic"
    k: int = 5
    retrieval_mode: RetrievalMode | None = None

    @field_validator("question")
    @classmethod
    def check_question(cls, v: str) -> str:
        return validate_question(v)
```

- `@field_validator` (v2) replaced `@validator` (v1). Must be paired with `@classmethod`, and order matters — `field_validator` outermost.
- It **returns** the value, so the stripped question is what reaches the handler.
- Raising `ValueError` inside a validator → FastAPI converts to HTTP 422 automatically. You don't write the error-mapping code.
- `ProviderName` and `RetrievalMode` as field types means invalid providers are rejected at the boundary with a structured error listing the valid options.



### Separate In/Out models

`QueryIn` → `QueryOut`, `ChunkOut`, `AgentStepOut`, `AgentOut`. Why not return the dataclasses directly?

- `RAGResult` and `AgentRun` are internal; changing them shouldn't break API consumers.
- `AgentStepOut` deliberately **omits** `tool_output` — tool outputs contain full retrieved chunks and would bloat every response. Response models are where you decide what leaves the process.
- `response_model=QueryOut` gives you OpenAPI schema generation and response validation for free.



### The health endpoint

```python
@app.get("/health")
def health() -> dict:
    chunks = collection_chunk_count()
    status = "ok" if chunks > 0 else "degraded"
    return {"status": status, "corpus_chunks": chunks,
            "retrieval_mode": get_retrieval_mode().value,
            "message": "ready" if chunks > 0 else "run: python scripts/ingest_corpus.py"}
```

Three properties of a *good* health check, all present:

1. **It checks a real dependency**, not just "the process is alive". `collection_chunk_count()` actually queries Chroma.
2. **It degrades rather than lying.** A RAG app with an empty index returns confident-sounding garbage. `degraded` surfaces that.
3. **It carries the remediation.** The `message` field tells you the exact command to run.

And `collection_chunk_count()` swallows exceptions to return `0` — a health endpoint that 500s is useless to a load balancer.

The smoke test (`tests/e2e/test_api_smoke.py`) asserts the *shape* of the response, not the values — so it passes with or without an ingested corpus, and runs with no API keys via `fastapi.testclient.TestClient` (which uses an in-process ASGI transport, no real socket).

---



## 9. `.env` loading — where and why

Three `load_dotenv()` calls exist:


| File                                 | Why                                                                         |
| ------------------------------------ | --------------------------------------------------------------------------- |
| `conftest.py` (root)                 | pytest imports test modules before any app code runs; env must be set first |
| `eval/conftest.py::pytest_configure` | belt-and-braces before eval tests import providers                          |
| `app/main.py`, `app/streamlit_ui.py` | entry points for the running app                                            |


Note `app/streamlit_ui.py` puts `load_dotenv()` **above** the `from app.agent import run_agent` imports, violating PEP 8 import ordering deliberately — because `app.embeddings` reads env vars at import time. That's a real ordering hazard worth recognizing: *any* module that reads config at import time forces this kind of contortion. It's an argument for the function-based config style used in `app/retrieval/config.py`.

---



## Exercises

1. Convert `LLMProvider` from `ABC` to `typing.Protocol`. What breaks? What improves? Write down when you'd choose each. (Hint: Protocol gives structural typing and no inheritance requirement; ABC gives runtime enforcement and a place to put shared code.)
2. `_is_retryable` matches on strings. Rewrite it to use the Anthropic/OpenAI SDK exception classes, and add tests. What's the tradeoff in coupling?
3. Add a `MAX_K` guard so `k=10000` can't be requested via `/query`. Where does it belong — `guards.py`, the Pydantic model, or both? Defend your answer.
4. `MAX_QUESTION_CHARS` is read at import time. Write a test that demonstrates the consequence, then decide whether to change it.
5. Add a `/ready` endpoint distinct from `/health` (readiness vs liveness). What should each check?



## Interview questions this section answers

- "How do you avoid vendor lock-in with LLM providers?"
- "What's your retry strategy, and what do you *not* retry?"
- "How do you handle configuration across local, CI, and production?"
- "What does a good health check look like for an AI service?"
- "How do you manage dependency risk in the ML ecosystem?"

