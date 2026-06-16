"""Langfuse observability — traces every RAG and agent call when keys are set.

Study note: observability is not optional in AI QA. You need traces to debug
*why* faithfulness dropped (bad retrieval? prompt drift? model change?).

Uses Langfuse SDK v3+ API (start_as_current_observation).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Literal, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

ObservationType = Literal[
    "span", "generation", "embedding", "agent", "tool", "chain", "retriever", "evaluator", "guardrail"
]

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
def trace(
    name: str,
    *,
    input: Any = None,
    metadata: dict | None = None,
    as_type: ObservationType = "span",
):
    """Langfuse observation context — no-op when keys are missing."""
    lf = get_langfuse()
    if lf is None:
        yield None
        return

    try:
        observation_cm = lf.start_as_current_observation(
            name=name,
            as_type=as_type,
            input=input,
            metadata=metadata or {},
        )
    except Exception:
        # Langfuse unavailable — degrade gracefully without breaking the app
        yield None
        return

    with observation_cm as obs:
        try:
            yield obs
        except Exception as e:
            try:
                obs.update(level="ERROR", status_message=str(e))
            except Exception:
                pass
            raise


def observe(
    name: str | None = None,
    as_type: ObservationType = "span",
) -> Callable[[F], F]:
    """Decorator wrapping a function in a Langfuse observation."""

    def decorator(fn: F) -> F:
        trace_name = name or fn.__name__

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with trace(
                trace_name,
                input={"args": _safe(args), "kwargs": _safe(kwargs)},
                as_type=as_type,
            ) as obs:
                result = fn(*args, **kwargs)
                if obs is not None:
                    obs.update(output=_safe(result))
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
