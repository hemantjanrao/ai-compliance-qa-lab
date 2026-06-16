"""Pytest hooks — report collection, agent trajectory cache.

Study note: caching trajectories teaches CI cost control. One agent run per
golden case, shared across tool-selection / content / loop tests.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from eval.reporting import ReportCollector

CACHE_DIR = Path(".eval_cache/agent")
USE_CACHE = os.getenv("EVAL_USE_CACHE", "1") != "0"


def pytest_configure(config):
    ReportCollector.reset()


def pytest_sessionfinish(session, exitstatus):
    if session.config.getoption("--collect-only", default=False):
        return
    data = ReportCollector.data()
    has_metrics = bool(data.get("ragas") or data.get("latency_p95_ms"))
    has_adversarial = (data.get("adversarial") or {}).get("rag_passed") is not None
    if has_metrics or has_adversarial:
        ReportCollector.save()


@pytest.fixture(scope="session")
def agent_cache_dir() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def _cache_key(question: str) -> str:
    return hashlib.sha256(question.encode()).hexdigest()[:16]


def load_cached_agent_run(question: str, cache_dir: Path):
    from app.agent.runner import AgentRun, TrajectoryStep

    path = cache_dir / f"{_cache_key(question)}.json"
    if not USE_CACHE or not path.exists():
        return None
    data = json.loads(path.read_text())
    return AgentRun(
        question=data["question"],
        final_answer=data["final_answer"],
        trajectory=[TrajectoryStep(**s) for s in data["trajectory"]],
        steps_taken=data["steps_taken"],
        stopped_reason=data["stopped_reason"],
        input_tokens=data["input_tokens"],
        output_tokens=data["output_tokens"],
    )


def save_cached_agent_run(run, cache_dir: Path) -> None:
    from dataclasses import asdict

    path = cache_dir / f"{_cache_key(run.question)}.json"
    path.write_text(json.dumps(asdict(run), indent=2))


@pytest.fixture
def agent_run_for_case(agent_cache_dir, request):
    """Parametrize with a golden case dict; returns cached AgentRun."""
    case = request.param
    question = case["question"]
    run = load_cached_agent_run(question, agent_cache_dir)
    if run is None:
        from app.agent import run_agent

        run = run_agent(question)
        save_cached_agent_run(run, agent_cache_dir)
    return case, run
