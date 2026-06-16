"""Collect eval metrics during pytest runs and write JSON reports.

Study note: separating *measurement* (tests) from *gating* (eval/gate.py) mirrors
how production teams run eval harnesses and compare artifacts in CI.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

THRESHOLDS_PATH = Path("eval/thresholds.yaml")
REPORTS_DIR = Path("eval/reports")
CURRENT_REPORT = REPORTS_DIR / "current.json"
BASELINE_REPORT = REPORTS_DIR / "baseline.json"


def load_thresholds() -> dict[str, Any]:
    if not THRESHOLDS_PATH.exists():
        return {}
    return yaml.safe_load(THRESHOLDS_PATH.read_text()) or {}


class ReportCollector:
    """Session-scoped metric store; reset between pytest runs."""

    _data: dict[str, Any] = {}

    @classmethod
    def reset(cls) -> None:
        cls._data = {
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "commit": _git_commit(),
            "ragas": {},
            "latency_p95_ms": {},
            "cost_per_query_usd": {},
            "adversarial": {"rag_passed": None, "agent_passed": None},
            "agent": {"cases_run": 0},
            "deepeval": {},
        }

    @classmethod
    def set(cls, path: str, value: Any) -> None:
        """Set nested key like 'ragas.anthropic.faithfulness'."""
        parts = path.split(".")
        node = cls._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    @classmethod
    def increment(cls, path: str, amount: int = 1) -> None:
        parts = path.split(".")
        node = cls._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = node.get(parts[-1], 0) + amount

    @classmethod
    def data(cls) -> dict[str, Any]:
        return cls._data

    @classmethod
    def save(cls, path: Path = CURRENT_REPORT) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        cls._data["timestamp"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(cls._data, indent=2) + "\n")
        return path


def _git_commit() -> str:
    import subprocess

    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"
