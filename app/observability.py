"""Langfuse observability — traces every RAG and agent call when keys are set.

Study note: observability is not optional in AI QA. You need traces to debug
*why* faithfulness dropped (bad retrieval? prompt drift? model change?).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_langfuse = None
_enabled: bool | None = None


def _is_enabled() -> bool:
    global _enabled
    if _enabled is None:
        _enabled = bool(
            os.getenv("LANGFUSE_PUBLIC_KEY")
            and os.getenv("LANGFUSE_SECRET_KEY")
        )
    return _enabled


def get_langfuse():
    global _langfuse
    if not _is_enabled():
        return None
    if _langfuse is None:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
    return _langfuse


def flush() -> None:
    lf = get_langfuse()
    if lf is not None:
        lf.flush()


@contextmanager
def trace(name: str, *, input: Any = None, metadata: dict | None = None):
    """Langfuse trace context — no-op when keys are missing (unit tests, local dev)."""
    lf = get_langfuse()
    if lf is None:
        yield None
        return

    t = lf.trace(name=name, input=input, metadata=metadata or {})
    try:
        yield t
    except Exception as e:
        t.update(level="ERROR", status_message=str(e))
        raise
    finally:
        flush()


def observe(name: str | None = None) -> Callable[[F], F]:
    """Decorator wrapping a function in a Langfuse trace."""

    def decorator(fn: F) -> F:
        trace_name = name or fn.__name__

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with trace(trace_name, input={"args": _safe(args), "kwargs": _safe(kwargs)}) as t:
                result = fn(*args, **kwargs)
                if t is not None:
                    t.update(output=_safe(result))
                return result

        return wrapper  # type: ignore[return-value]

    return decorator


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
