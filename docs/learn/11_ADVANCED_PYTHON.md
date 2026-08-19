# 11 — Advanced Python, Grounded in This Repo

Every concept below is anchored to a real file. Read a section, then open the file and read the code with the concept in mind. Where the repo doesn't demonstrate something important, it's marked **[not in repo]** and taught with a minimal example.

---

## 1. Type system

### `Literal` — closed sets of string values

```python
# app/providers.py
ProviderName = Literal["anthropic", "openai"]
# app/embeddings.py
EmbeddingProvider = Literal["local", "openai"]
# app/observability.py
ObservationType = Literal["span", "generation", "embedding", "agent", "tool",
                          "chain", "retriever", "evaluator", "guardrail"]
```

`Literal` turns a stringly-typed API into a checked one. `get_provider("antropic")` is a mypy error, and Pydantic uses it to reject invalid values at the HTTP boundary with a helpful message.

**When to use `Literal` vs `Enum`:**

| | `Literal` | `Enum` |
|---|---|---|
| Values | Plain strings — no import needed at call sites | Members — `RetrievalMode.BASIC` |
| Best for | Small, stable sets used as data (`"anthropic"`) | Sets with behavior, iteration, or reverse lookup |
| Serialization | Trivially JSON | Needs `.value` unless `str` mixin |

The repo uses both: `Literal` for provider names (just data) and `Enum` for `RetrievalMode` (compared with `==`, needs `.value` for reports, benefits from `str` mixin).

### `str, Enum` mixin

```python
# app/retrieval/config.py
class RetrievalMode(str, Enum):
    BASIC = "basic"
    ADVANCED = "advanced"
```

Multiple inheritance from `str` means members *are* strings: usable in f-strings, JSON-serializable, accepted by Pydantic directly. Python 3.11+ has `StrEnum` which does this more explicitly — a trivial modernization.

Without the mixin you'd need `.value` everywhere and custom JSON encoders.

### `TypeVar` and generic decorators

```python
# app/observability.py
F = TypeVar("F", bound=Callable[..., Any])

def observe(name=None, as_type="span") -> Callable[[F], F]:
```

`bound=Callable[..., Any]` constrains `F` to callables. `Callable[[F], F]` says "takes a function, returns a function of the same type" — so the decorated function keeps its type.

The `# type: ignore[return-value]` inside admits mypy can't verify this. **The modern fix is `ParamSpec` (PEP 612):**

```python
from typing import ParamSpec, TypeVar, Callable
P = ParamSpec("P")
R = TypeVar("R")

def observe(name: str | None = None) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            ...
            return fn(*args, **kwargs)
        return wrapper
    return decorator
```

`P.args` / `P.kwargs` preserve the exact parameter signature — no `type: ignore` needed. **Doing this refactor is exercise #1 for Day 7.**

### `TYPE_CHECKING` — imports for types only

```python
# app/rag.py, app/retrieval/pipeline.py
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from chromadb.api.models.Collection import Collection

def _get_collection() -> Collection: ...
```

`TYPE_CHECKING` is `False` at runtime, `True` for type checkers. The import never executes — avoiding a heavy import and any circular-import risk — but mypy still resolves the annotation.

This works because `from __future__ import annotations` (present at the top of every module here) makes all annotations lazy strings (PEP 563). Without it you'd need quoted forward references: `-> "Collection"`.

### `X | None` and PEP 604

```python
def rerank_model_name() -> str: ...
def load(cls, path: Path) -> BM25Index | None: ...
def extract_article_filter(question: str) -> int | None: ...
```

`X | Y` replaces `Optional[X]` / `Union[X, Y]` (3.10+, or any version with `from __future__ import annotations`). Note the semantic distinction the repo respects: `BM25Index | None` means "may legitimately be absent" and callers must handle it — that's the graceful-degradation contract from [`03`](03_RETRIEVAL_PIPELINE.md).

### **[not in repo] `Protocol` — structural typing**

```python
from typing import Protocol

class LLMProviderProto(Protocol):
    def generate(self, system: str, user: str, max_tokens: int = 1024) -> LLMResponse: ...
```

Any object with a matching `generate` satisfies this — **no inheritance required**. Compare `app/providers.py`'s ABC, which requires subclassing.

| | ABC | Protocol |
|---|---|---|
| Enforcement | Runtime (can't instantiate incomplete subclass) | Static only (unless `@runtime_checkable`) |
| Requires inheritance | Yes | No |
| Third-party types | Must wrap | Just work if shape matches |
| Shared implementation | Yes, put it on the base | No |

Protocol shines when you want to accept *anyone's* object — a mock, a third-party client, a test double — without them importing your base class. In `tests/test_rag_security.py`, `MagicMock` satisfies the shape but not the ABC; nothing checks `isinstance`, so it works either way. **Refactoring `LLMProvider` to a Protocol and arguing the tradeoff is a Day 7 exercise.**

---

## 2. Dataclasses

### The repo's eight dataclasses

| Class | File | Notable |
|---|---|---|
| `LLMResponse` | `app/providers.py` | Vendor-normalizing adapter |
| `RetrievedChunk` | `app/retrieval/types.py` | 3 fields, own module to avoid circular imports |
| `BM25Chunk` | `app/retrieval/bm25_index.py` | Simple record |
| `RAGResult` | `app/rag.py` | Defaulted field last |
| `TrajectoryStep` | `app/agent/runner.py` | Tagged union via `type` |
| `AgentRun` | `app/agent/runner.py` | `default_factory`, helper methods |
| `RagEvalRow` | `eval/deepeval_helpers.py` | Test-data aggregate |
| `GateFailure`, `GateResult` | `eval/gate.py` | Structured results |

### `field(default_factory=...)` — the mutable-default rule

```python
@dataclass
class AgentRun:
    trajectory: list[TrajectoryStep] = field(default_factory=list)
```

`trajectory: list = []` would raise `ValueError: mutable default` in a dataclass (the decorator explicitly guards this). In a plain function signature it wouldn't raise — it would silently share one list across all calls, which is the classic Python bug. **The dataclass protects you; a function signature doesn't.**

### Field ordering

```python
@dataclass
class RAGResult:
    answer: str
    ...
    retrieval_mode: str = "basic"      # ← must be last
```

Non-default fields cannot follow defaulted ones — same rule as function parameters, because `__init__` is generated from field order.

### `asdict` — recursive serialization

```python
# eval/conftest.py
path.write_text(json.dumps(asdict(run), indent=2))
...
AgentRun(..., trajectory=[TrajectoryStep(**s) for s in data["trajectory"]], ...)
```

`asdict` recurses into nested dataclasses, lists, dicts, and tuples. **This one function is why the trajectory cache is a two-liner.** Reconstruction uses `**s` dict unpacking into the constructor.

⚠️ `asdict` deep-copies and fails on non-serializable field values. `TrajectoryStep.tool_output` is `Any` — if a tool ever returned a non-JSON-serializable object, caching would break. Currently safe because all four tools return plain dicts.

### `hasattr(obj, "__dataclass_fields__")`

```python
# app/observability.py::_safe
if hasattr(obj, "__dataclass_fields__"):
    from dataclasses import asdict
```

Duck-typed dataclass detection avoiding a module-level import. `dataclasses.is_dataclass(obj)` is the official API and does essentially this. Both fine; know that `__dataclass_fields__` is the underlying marker attribute.

### **[not in repo] `frozen=True` and `slots=True`**

```python
@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    text: str
    source: str
    distance: float
```

- `frozen=True` → immutable, hashable, usable as a dict key or in a set. `RetrievedChunk` is never mutated after construction — it's a natural candidate.
- `slots=True` (3.10+) → no `__dict__`, less memory, faster attribute access. Meaningful when you create thousands (chunks, trajectory steps).

Try it and see what breaks. Nothing should.

---

## 3. Decorators

### The three shapes

**a) Plain decorator** — `@wraps(fn)` in `app/observability.py`.

**b) Decorator factory (takes arguments)** — the canonical three-level nest:

```python
def observe(name=None, as_type="span"):        # ① config
    def decorator(fn):                          # ② receives the function
        @wraps(fn)
        def wrapper(*args, **kwargs):           # ③ replaces the function
            ...
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@observe(name="retrieve", as_type="retriever")  # ← must be *called*
def retrieve(...): ...
```

**c) Pre-configured decorator object** — `app/providers.py`:

```python
_retry = retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30),
               retry=retry_if_exception(_is_retryable))

class AnthropicProvider(LLMProvider):
    @_retry
    def generate(self, ...): ...
```

`tenacity.retry(...)` returns a decorator; binding it to `_retry` builds the config **once** and reuses it across both provider classes. Better than repeating the config, and it makes "our retry policy" a single named object.

### `@wraps` — non-negotiable

```python
from functools import wraps

@wraps(fn)
def wrapper(*args, **kwargs): ...
```

Copies `__name__`, `__qualname__`, `__doc__`, `__module__`, `__dict__`, and sets `__wrapped__`. Without it:
- `retrieve.__name__` is `"wrapper"` — and `observe`'s `trace_name = name or fn.__name__` would produce `"wrapper"` spans on stacked decorators
- pytest introspection, `inspect.signature`, and `help()` all break

### **[not in repo] Decorator that works with and without parentheses**

Classic interview question:

```python
def observe(fn=None, *, name=None, as_type="span"):
    def decorator(f):
        @wraps(f)
        def wrapper(*a, **kw):
            ...
            return f(*a, **kw)
        return wrapper
    if fn is None:            # called as @observe(...) — return the decorator
        return decorator
    return decorator(fn)      # called as @observe — apply immediately
```

The trick is the `fn=None` first positional plus keyword-only config.

### `@lru_cache` — memoization and lazy singletons

```python
# app/retrieval/reranker.py
@lru_cache(maxsize=1)
def _get_cross_encoder():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(rerank_model_name())
```

Zero-arg function + `maxsize=1` = **lazy singleton**. The expensive model loads once per process. Thread-safe for the caching itself.

Requirements and gotchas:
- Arguments must be **hashable** (no dicts or lists)
- The cache holds strong references — a cache on a method keeps `self` alive forever (memory leak)
- `functools.cache` (3.9+) = `lru_cache(maxsize=None)`
- `.cache_clear()` exists and is essential for testability

**Where the repo should use it but doesn't:**
- `eval/reporting.py::load_thresholds` — re-reads and re-parses YAML on every call
- `app/embeddings.py::get_chroma_embedding_function` — may reload the model per call in eval loops
- `app/observability.py::_is_enabled` — hand-rolls the same memoization with a tri-state global

### `@contextmanager`

```python
from contextlib import contextmanager

@contextmanager
def trace(name, *, input=None, metadata=None, as_type="span"):
    lf = get_langfuse()
    if lf is None:
        yield None            # ← must yield exactly once
        return
    with observation_cm as obs:
        try:
            yield obs
        except Exception as e:
            obs.update(level="ERROR", status_message=str(e))
            raise
```

Generator → context manager. Before `yield` = `__enter__`; the yielded value = the `as` target; after `yield` = `__exit__`. **An exception in the `with` body is thrown into the generator at the `yield` point**, which is why `try/except` around `yield` intercepts it.

Rules: yield **exactly once**; if you don't re-raise, you swallow the exception (here it deliberately re-raises).

Related, worth knowing: `contextlib.ExitStack` (dynamic numbers of context managers), `contextlib.suppress` (cleaner than `try/except: pass`), `contextlib.asynccontextmanager`.

### **[not in repo] Class-based decorators and descriptors**

```python
class CountCalls:
    def __init__(self, fn):
        self.fn, self.count = fn, 0
        wraps(fn)(self)
    def __call__(self, *a, **kw):
        self.count += 1
        return self.fn(*a, **kw)
```

⚠️ This breaks on **methods** because the class instance isn't a descriptor — `self` won't bind. Fixing it requires implementing `__get__`:

```python
    def __get__(self, obj, objtype=None):
        return functools.partial(self.__call__, obj)
```

That's the descriptor protocol, and it's the same machinery behind `@property`, `@classmethod`, `@staticmethod`, and every ORM field. Worth understanding even though the repo doesn't use it.

---

## 4. ABCs and inheritance

```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system: str, user: str, max_tokens: int = 1024) -> LLMResponse: ...
```

`ABC` sets `ABCMeta` as the metaclass, which checks at **instantiation** that all abstract methods are implemented. `LLMProvider()` raises `TypeError`. So does a subclass that forgets `generate`.

The `...` body is idiomatic for abstract methods and Protocol members — signals "no implementation" more clearly than `pass`.

### **[not in repo] `__init_subclass__` — auto-registration**

A cleaner alternative to the manual `TOOLS` dict in `app/agent/tools.py`:

```python
class Tool:
    registry: dict[str, type["Tool"]] = {}
    def __init_subclass__(cls, /, name: str, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.name = name
        Tool.registry[name] = cls

class ComputeFine(Tool, name="compute_fine"):
    ...
# Tool.registry is now populated automatically
```

`__init_subclass__` runs on the *parent* whenever a subclass is defined. It's the lightweight alternative to a metaclass and covers most registration use cases. Compare `metaclass=ABCMeta`, which is the heavyweight version.

---

## 5. Comprehensions, generators, and iteration

### Generator expressions avoid intermediate lists

```python
# app/rag.py
context = "\n\n".join(f"[Source: {c.source}]\n{c.text}" for c in chunks)

# app/agent/runner.py
run.final_answer = "\n".join(s.text for s in run.trajectory if s.type == "text" and s.text)

# app/retrieval/bm25_index.py
sorted(((self.chunks[i].chunk_id, float(scores[i])) for i in range(len(self.chunks))), ...)
```

No list is materialized. For `join` this is idiomatic — though note that `str.join` internally materializes anyway, so the gain is marginal there; the real win is on large lazy pipelines.

### `next()` with a generator — first match

```python
# app/agent/tools.py
order = ["unacceptable", "high", "limited", "minimal"]
tier = next(t for t in order if t in matches)
```

Stops at the first match — no full list built. ⚠️ Raises `StopIteration` if nothing matches. Safe here by construction, but `next(gen, default)` is the defensive form.

### `any()` / `all()` short-circuit

```python
# eval/agent/test_tool_selection.py
ok = any(all(t in called for t in option) for option in case["expected_tools_any_of"])
```

Nested short-circuit: `all` stops at the first missing tool, `any` stops at the first satisfied option. Reads exactly like the spec: "any acceptable option, all of whose tools were called."

### Dict comprehension with a filter pass

```python
# app/agent/tools.py
matches = {tier: [k for k in keywords if k in text] for tier, keywords in RISK_TIERS.items()}
matches = {t: m for t, m in matches.items() if m}   # drop empties
```

Two passes for readability. A single pass with a walrus is possible but less clear.

### `zip` — parallel iteration

```python
# app/retrieval/pipeline.py
for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
```

⚠️ `zip` silently truncates to the shortest iterable. **Python 3.10+ has `zip(..., strict=True)`** which raises on length mismatch — the safer choice when the lists *must* be the same length, as here. Good hardening exercise.

### `Counter` — frequency counting

```python
# eval/agent/test_tool_selection.py
signatures = [(s.tool_name, json.dumps(s.tool_input, sort_keys=True)) for s in ...]
counts = Counter(signatures)
```

Requires **hashable** elements — hence the tuple-of-strings, hence `json.dumps(sort_keys=True)` to canonicalize the unhashable dict. That canonicalization trick generalizes: any time you need to hash a dict, serialize it deterministically.

### **[not in repo] Generators with state, `yield from`, and the iterator protocol**

```python
def read_golden_streaming(path: Path):
    with path.open() as f:
        for line in f:                # ← lazy, one line at a time
            if line.strip():
                yield json.loads(line)
```

Compare `eval/helpers.py::load_golden_rag`, which does `read_text().splitlines()` — the whole file in memory. Fine at 23 lines, wrong at 23 million. The generator version has O(1) memory.

Know also: `yield from` (delegation), generator `.send()`/`.throw()`/`.close()`, and that `@contextmanager` is built on exactly this machinery.

---

## 6. Exceptions

### Custom messages as contracts

```python
# app/agent/tools.py
raise KeyError(f"Hallucinated tool: '{name}'. Available: {list(TOOLS.keys())}")
```

Two test files grep for the literal `"Hallucinated tool"`. **The message is API.** If that bothers you (it should, slightly), extract it to a constant.

Note the message includes the valid options — errors should tell you what to do, not just what went wrong.

### Exception unwrapping

```python
# app/env_check.py
if isinstance(exc, RetryError):
    if exc.last_attempt and exc.last_attempt.exception():
        exc = exc.last_attempt.exception()
```

Retry wrappers hide the real error. **Always unwrap before formatting.** Related: `raise X from Y` sets `__cause__` explicitly; `raise X` inside an `except` sets `__context__` implicitly.

### Bare `except Exception` — three uses, three verdicts

| Location | Verdict |
|---|---|
| `scripts/ingest_corpus.py` — `delete_collection` | ⚠️ acceptable (collection may not exist) but too broad |
| `app/retrieval/pipeline.py` — filtered query fallback | ⚠️ hides genuine bugs; should log |
| `app/observability.py` — three nested levels | ✅ correct — monitoring must never break the app |

The rule: broad catches are justified when the alternative is worse than the silent failure. In observability, that's true. In a retrieval fallback, it's arguable. In ingestion, it's laziness.

Note `app/observability.py` catches, records, and **re-raises** — it never swallows an application exception.

### `pytest.raises` with `match`

```python
with pytest.raises(KeyError, match="Hallucinated tool"):
    execute_tool("send_email", {"to": "attacker@evil.com"})
```

`match` is a **regex searched against `str(exception)`**. Asserting on the message, not just the type, is what makes the test meaningful.

---

## 7. Standard library you should know cold

### `pathlib.Path`

Used throughout. `/` for joining, `.exists()`, `.read_text()`, `.write_text()`, `.mkdir(parents=True, exist_ok=True)`, `.unlink(missing_ok=True)`, `.is_dir()`.

```python
# eval/test_promptfoo.py
OUTPUT.unlink(missing_ok=True)      # ← prevents reading a stale artifact
```

`missing_ok=True` (3.8+) replaces `try/except FileNotFoundError`.

### `hashlib`

```python
# eval/conftest.py
hashlib.sha256(raw.encode()).hexdigest()[:16]
```

`.encode()` is required — hashes take bytes. `[:16]` = 64 bits, ample for a per-run cache.

### `json` — canonical serialization

```python
json.dumps(s.tool_input, sort_keys=True)      # canonical form for hashing/comparison
json.dumps(output)[:8000]                     # truncate before sending to the model
json.dumps(cls._data, indent=2) + "\n"        # human-readable + trailing newline for git
```

Three different uses, three different flag choices. The trailing `"\n"` matters — files without one produce noisy diffs.

### `datetime` — always timezone-aware

```python
datetime.now(timezone.utc).isoformat()
```

Never `datetime.now()` (naive local time) for anything persisted or compared. 3.11+ has `datetime.UTC` as an alias.

### `subprocess`

```python
subprocess.run([sys.executable, str(GENERATOR)], check=True)
subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
```

- **List form, never `shell=True`** — no shell injection.
- **`sys.executable`** not `"python"` — uses the same interpreter running pytest, so venv-correct.
- **`check=True`** raises `CalledProcessError` on non-zero exit.
- **`stderr=DEVNULL`** suppresses git's noise when not in a repo.

### `argparse`

```python
def main(argv: list[str] | None = None) -> int:
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args(argv)
```

`argv=None` → testable. `action="store_true"` → flags. `type=Path` → automatic conversion.

### `os.getenv` with defaults

```python
os.getenv("CHROMA_PATH", "./chroma_db")        # optional, has a fallback
os.environ["OPENAI_API_KEY"]                    # required — KeyError if missing
```

The distinction is deliberate: `os.environ[...]` for things that *must* be set.

### `shutil`, `importlib.util`, `re`, `math`, `time`

```python
shutil.copy(args.current, args.baseline)              # gate promotion
shutil.rmtree(deepeval_key)                           # cleanup
importlib.util.spec_from_file_location(...)           # load a non-package script
re.compile(r"\bArticle\s+(\d{1,3})\b")                # compile once at module level
math.isnan(value)                                     # NaN never equals itself
time.perf_counter()                                   # monotonic, high-resolution
```

**`math.isnan`** matters: `nan == nan` is `False`, so you cannot test for NaN with `==`.
**`time.perf_counter`** not `time.time` for durations — monotonic and immune to clock adjustments.

---

## 8. pytest, deeply

### Fixtures

```python
@pytest.fixture(scope="session")
def agent_cache_dir() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR
```

Scopes: `function` (default) → `class` → `module` → `package` → `session`.

### Yield fixtures = setup/teardown

```python
@pytest.fixture(scope="session", autouse=True)
def _record_adversarial_rag_passed(request):
    yield                                    # ← everything after runs at teardown
    if request.session.testsfailed == 0:
        ReportCollector.set("adversarial.rag_passed", True)
```

`autouse=True` = applies without being requested. Combined with `scope="session"`, this is a session-end hook without writing a plugin.

### `request` — the introspection object

- `request.param` — the parametrized value (indirect parametrization)
- `request.session.testsfailed` — global failure counter
- `request.config` — the pytest config
- `request.node` — the current test item

### Indirect parametrization

```python
@pytest.fixture
def agent_run_for_case(agent_cache_dir, request):
    case = request.param
    ... return (case, run)

@pytest.mark.parametrize("agent_run_for_case", CASES, indirect=True, ids=lambda c: c["id"])
def test_tool_selection(agent_run_for_case):
    case, run = agent_run_for_case
```

Values go to the **fixture** via `request.param`; the test receives the fixture's return value. The fixture becomes a parametrized factory.

`ids=lambda c: c["id"]` → `test_tool_selection[agent-001]` instead of `[case3]`.

### Stacked parametrize = Cartesian product

```python
@pytest.mark.parametrize("attack", DIRECT_INJECTIONS)      # 5
@pytest.mark.parametrize("provider", ["anthropic", "openai"])  # 2
def test_resists_direct_injection(attack, provider): ...   # → 10 cases
```

### `monkeypatch`

```python
monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-...")
monkeypatch.setattr(mod, "PDF_PATH", tmp_path / "missing.pdf")
```

Automatically undone at teardown. Also: `delenv`, `setitem`, `delattr`, `chdir`, `syspath_prepend`.

### `tmp_path`

Per-test temporary directory as a `Path`. Auto-cleaned. Use it instead of `tempfile` boilerplate.

### The hooks used here

| Hook | When | Used for |
|---|---|---|
| `pytest_configure` | after config, before collection | `load_dotenv`, `ReportCollector.reset()` |
| `pytest_collection_modifyitems` | after collection | dynamic skipping by provider/keys |
| `pytest_sessionfinish` | after all tests | conditional report save |

Others worth knowing: `pytest_runtest_setup`, `pytest_addoption` (custom CLI flags), `pytest_generate_tests` (programmatic parametrization).

### Markers

```toml
markers = ["eval: ...", "adversarial: ...", "slow: ..."]
```

```bash
pytest -m "not slow"
pytest -m "eval and not slow"
```

Registering markers in config enables `--strict-markers`, which turns a typo'd marker into an error instead of a silently-never-selected test.

### `skip` vs `fail` — a real distinction

```python
except FileNotFoundError:
    pytest.skip("npx not available — install Node.js to run promptfoo")
except subprocess.CalledProcessError as e:
    pytest.fail(f"promptfoo eval failed (exit {e.returncode})")
```

Environment limitation → skip. Real failure → fail. Conflating them either hides bugs or produces red builds on incomplete environments.

### conftest layering

Root `conftest.py` applies to everything; `eval/conftest.py` only to `eval/`. The **absence** of `tests/conftest.py` structurally enforces that unit tests don't depend on eval infrastructure.

---

## 9. Mocking

```python
from unittest.mock import MagicMock, patch

@patch("app.rag.get_provider")                 # ← patch where USED, not where defined
def test_resists_poisoned_retrieval_chunk(mock_get_provider):
    mock_llm = MagicMock()
    mock_llm.generate.return_value = MagicMock(text="...", input_tokens=100, ...)
    mock_get_provider.return_value = mock_llm
```

### The #1 mocking rule

`app/rag.py` did `from app.providers import get_provider`, which **binds the object into `app.rag`'s namespace**. Patching `app.providers.get_provider` rebinds the name in the *source* module — `app.rag`'s reference still points at the original. You must patch `app.rag.get_provider`.

Mnemonic: **patch where it's looked up, not where it's defined.**

### `MagicMock` vs `Mock` vs `create_autospec`

| | Behavior |
|---|---|
| `Mock` | Any attribute access returns a new Mock |
| `MagicMock` | Same, plus magic methods (`__len__`, `__iter__`, `__enter__`, …) configured |
| `create_autospec(target)` | Mock **constrained to the real signature** — calling with wrong args raises |

`create_autospec` is the safest and under-used. A `MagicMock` happily accepts `mock.generat(...)` (typo) and returns a Mock, so a test can pass against an API that no longer exists.

### Inspecting calls

```python
call_kwargs = mock_llm.generate.call_args
user_prompt = call_kwargs.kwargs.get("user") or call_kwargs[1].get("user") or call_kwargs[0][1]
```

`call_args` is a `Call` object supporting `.args`, `.kwargs`, and legacy tuple indexing (`[0]` = args, `[1]` = kwargs). The triple fallback handles both call styles.

Also: `.call_count`, `.call_args_list`, `.assert_called_once_with(...)`, `.assert_not_called()`.

⚠️ Typo'd assert methods (`assert_called_once` vs `assert_called_once_with`) silently pass on a plain Mock. `Mock(spec=...)` or `create_autospec` prevents this.

---

## 10. Import machinery

### Loading a module from a path

```python
# tests/test_ingest_guards.py
spec = importlib.util.spec_from_file_location("ingest_corpus", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
```

`scripts/` isn't a package, so normal import fails. This is the same three-step machinery `import` uses internally: build a spec → create the module object → execute the code in its namespace.

### Deferred imports for cost

```python
# app/retrieval/reranker.py
def _get_cross_encoder():
    from sentence_transformers import CrossEncoder   # torch: seconds + hundreds of MB
    return CrossEncoder(rerank_model_name())

# app/observability.py
def get_langfuse():
    from langfuse import Langfuse
```

Module-scope imports would slow every `pytest` collection. Deferring means the cost is paid only when used.

### Deferred imports for circularity

```python
# eval/conftest.py
def load_cached_agent_run(...):
    from app.agent.runner import AgentRun, TrajectoryStep
```

`eval/conftest.py` loads before app modules; a top-level import could create a cycle. Function-scope import defers resolution to call time.

Related structural fix: `app/retrieval/types.py` exists **solely** to hold `RetrievedChunk` so `app/rag.py` and `app/retrieval/pipeline.py` can both import it without importing each other. **Extracting shared types into a leaf module is the standard cure for import cycles.**

### `__init__.py` as a public API

```python
# app/retrieval/__init__.py
from app.retrieval.config import RetrievalMode, get_retrieval_mode
from app.retrieval.pipeline import retrieve_chunks
__all__ = ["RetrievalMode", "get_retrieval_mode", "retrieve_chunks"]

# app/agent/__init__.py
from app.agent.runner import AgentRun, TrajectoryStep, run_agent  # noqa: F401
```

`__all__` declares the public surface (controls `from x import *` and documents intent). `# noqa: F401` silences ruff's "imported but unused" — the import *is* the point.

---

## 11. Concurrency **[mostly not in repo]**

The repo is synchronous throughout, with one relevant setting:

```toml
asyncio_mode = "auto"      # pyproject.toml
```

...and one consequence:

```python
FaithfulnessMetric(threshold=0.7, async_mode=False)   # "async off for pytest stability"
```

DeepEval's async mode conflicts with pytest-asyncio's auto mode. Real-world friction worth knowing.

### What you'd need for a concurrent version

**The obvious optimization** is in `eval/test_ragas.py`:

```python
for ex in golden:
    r = answer(ex["question"], provider=provider)   # 23 sequential network round trips
```

Concurrent version:

```python
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(lambda case: answer(case["question"], provider=provider), golden))
```

**Threads, not processes** — this is I/O-bound (network waits), and the GIL is released during I/O. `ProcessPoolExecutor` would be right for CPU-bound work (embedding, reranking).

### GIL essentials

- Only one thread executes Python bytecode at a time.
- The GIL is **released** during I/O and inside many C extensions (numpy, torch).
- So: threads for I/O-bound, processes (or C extensions) for CPU-bound.
- Python 3.13 has an experimental free-threaded build; 3.12+ has per-interpreter GILs.

### asyncio, briefly

```python
async def answer_async(question: str) -> RAGResult: ...
results = await asyncio.gather(*[answer_async(q) for q in questions])
```

`async`/`await` is cooperative — one thread, many concurrent I/O waits, no thread overhead. Requires async-native clients all the way down (`AsyncAnthropic`, `AsyncOpenAI`). Mixing sync and async is the usual source of pain (`asyncio.run` inside a running loop, blocking calls starving the event loop).

⚠️ **The thread-safety gap in this repo:** `app/observability.py::get_langfuse` and `_is_enabled` use unguarded module globals. Under `ThreadPoolExecutor`, two threads could construct two clients. Harmless here, but it's the kind of thing to notice before adding concurrency. `@lru_cache` would make it safe.

---

## 12. Memory, GC, and performance **[not in repo]**

Worth knowing for senior interviews even though the repo doesn't exercise it.

### Reference counting + cycle collector

CPython frees objects when the refcount hits zero; a generational GC handles reference cycles. Consequences:

- `@lru_cache` on a method keeps `self` alive → leak. Use `weakref` or cache at module level.
- `__slots__` removes per-instance `__dict__` — meaningful for many small objects.
- Closures keep their captured variables alive — a decorator holding a large object pins it.

### Interning and identity

`is` compares identity, `==` compares value. Small ints (−5…256) and some strings are interned, which makes `is` *accidentally* work and then fail in production. **Only use `is` for `None`, `True`, `False`, and sentinels** — which is exactly what the repo does (`if value is None`, `is not True`).

That `is not True` in `eval/gate.py` is a good example of deliberate identity comparison: it distinguishes `True` from `None`/`False`/truthy-other.

### Profiling toolkit

```bash
python -m cProfile -s cumtime -m pytest tests/       # where is time going
python -m tracemalloc ...                            # where is memory going
pip install py-spy && py-spy top -- python ...       # sampling profiler, no code change
pip install memray                                   # allocation tracking
```

`timeit` for microbenchmarks. `time.perf_counter()` for wall-clock, as `eval/test_budget.py` does.

---

## 13. Style and tooling

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
```

**ruff** — linter + formatter, replacing flake8/isort/black. Fast enough to run on save.

**mypy** is in dev deps but not wired into CI. `mypy --strict app/` would be a strong addition, and the `# type: ignore` comments in `app/observability.py` and `app/embeddings.py` mark exactly where the type story is weakest.

`from __future__ import annotations` appears at the top of **every** module. It makes annotations lazily-evaluated strings, enabling `X | None` on older versions, forward references without quotes, and `TYPE_CHECKING` imports. Consistency here is a good sign of a maintained codebase.

---

## Study path through this document

| Day | Sections | Anchor files |
|---|---|---|
| 1 | §1 types, §2 dataclasses | `providers.py`, `config.py`, `types.py` |
| 2 | §5 comprehensions, §7 stdlib | `bm25_index.py`, `fusion.py`, `query_expansion.py` |
| 3 | §6 exceptions, §9 mocking | `tools.py`, `test_rag_security.py` |
| 4 | §3 decorators, §8 pytest | `observability.py`, `conftest.py` |
| 5 | §8 pytest (parametrize), §7 stdlib | `test_deepeval.py`, `test_budget.py` |
| 6 | §7 argparse, §2 dataclasses | `gate.py` |
| 7 | §4 ABCs, §10 imports, §11 concurrency, §12 memory | consolidation + refactors |

## Exercises

1. Refactor `observe` from `TypeVar` to `ParamSpec`/`Concatenate`. Confirm the `# type: ignore` becomes unnecessary.
2. Convert `LLMProvider` from ABC to Protocol. What breaks? Which do you prefer here and why?
3. Add `@lru_cache` to `load_thresholds` and `get_chroma_embedding_function`. Measure. What's the invalidation risk?
4. Make `RetrievedChunk` `frozen=True, slots=True`. Anything break? Measure memory on 10,000 chunks.
5. Rewrite `_is_enabled` in `observability.py` using `functools.cache`. Is it clearer? Is it thread-safe now?
6. Write the `Tool` base class with `__init_subclass__` auto-registration and port the four tools to it.
7. Add `strict=True` to every `zip` in `app/retrieval/pipeline.py`. Does anything raise?
8. Parallelize `eval/test_ragas.py`'s answer generation with `ThreadPoolExecutor`. Measure the speedup. What breaks? (Hint: rate limits, and `observability` globals.)
9. Run `mypy --strict app/retrieval/` and fix everything.
10. Convert `load_golden_rag` to a generator. Where else would laziness help?
11. Write a decorator that works both as `@observe` and `@observe(name="x")`.
12. Profile `pytest tests/` with cProfile. What's the slowest thing in a suite with no network calls? Why?
