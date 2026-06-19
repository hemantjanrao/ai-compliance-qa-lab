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


def _eval_providers() -> list[str]:
    raw = os.getenv("EVAL_PROVIDERS", "anthropic,openai")
    return [p.strip() for p in raw.split(",") if p.strip()]


def _provider_api_ready(provider: str) -> bool:
    from app.env_check import anthropic_configured, openai_configured

    if provider == "anthropic":
        return anthropic_configured()
    if provider == "openai":
        return openai_configured()
    return False


def pytest_collection_modifyitems(config, items):
    """Skip API eval tests when keys missing; honour EVAL_PROVIDERS (CI uses anthropic only)."""
    if os.getenv("EVAL_SKIP_API") == "1":
        skip = pytest.mark.skip(reason="EVAL_SKIP_API=1")
        for item in items:
            if "eval" in item.keywords or "adversarial" in item.keywords:
                item.add_marker(skip)
        return

    allowed = _eval_providers()
    from app.env_check import anthropic_configured, openai_configured

    if not anthropic_configured() and not openai_configured():
        skip = pytest.mark.skip(reason="no LLM API keys configured")
        for item in items:
            if "eval" in item.keywords or "adversarial" in item.keywords:
                item.add_marker(skip)
        return

    for item in items:
        if not (hasattr(item, "callspec") and item.callspec and "provider" in item.callspec.params):
            continue
        provider = item.callspec.params["provider"]
        if provider not in allowed:
            item.add_marker(pytest.mark.skip(reason=f"provider {provider} not in EVAL_PROVIDERS"))
        elif not _provider_api_ready(provider):
            item.add_marker(pytest.mark.skip(reason=f"{provider} API key not configured"))


def pytest_configure(config):
    from dotenv import load_dotenv

    load_dotenv()  # ensure .env loaded before any eval test imports providers
    # DeepEval expects `.deepeval` to be a key file, not a directory.
    deepeval_key = Path(".deepeval")
    if deepeval_key.is_dir():
        import shutil

        shutil.rmtree(deepeval_key)
    ReportCollector.reset()


def pytest_sessionfinish(session, exitstatus):
    if session.config.getoption("--collect-only", default=False):
        return
    data = ReportCollector.data()
    has_metrics = bool(
        data.get("ragas") or data.get("latency_p95_ms") or data.get("deepeval") or data.get("promptfoo")
    )
    has_adversarial = (data.get("adversarial") or {}).get("rag_passed") is not None
    if has_metrics or has_adversarial:
        ReportCollector.save()


@pytest.fixture(scope="session")
def agent_cache_dir() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def _cache_key(question: str, case_id: str = "") -> str:
    raw = f"{case_id}:{question}" if case_id else question
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_cached_agent_run(question: str, cache_dir: Path, *, case_id: str = ""):
    from app.agent.runner import AgentRun, TrajectoryStep

    path = cache_dir / f"{_cache_key(question, case_id)}.json"
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


def save_cached_agent_run(run, cache_dir: Path, *, case_id: str = "") -> None:
    from dataclasses import asdict

    path = cache_dir / f"{_cache_key(run.question, case_id)}.json"
    path.write_text(json.dumps(asdict(run), indent=2))


@pytest.fixture
def agent_run_for_case(agent_cache_dir, request):
    """Parametrize with a golden case dict; returns cached AgentRun."""
    case = request.param
    question = case["question"]
    case_id = case.get("id", "")
    run = load_cached_agent_run(question, agent_cache_dir, case_id=case_id)
    if run is None:
        from app.agent import run_agent

        run = run_agent(question)
        save_cached_agent_run(run, agent_cache_dir, case_id=case_id)
    return case, run
