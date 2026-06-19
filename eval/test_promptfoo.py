"""promptfoo regression — full golden-set prompt v1 vs v2 comparison.

Generates tests from golden.jsonl, runs promptfoo, records pass rate to current.json.

Run:
  pytest eval/test_promptfoo.py -v -m eval
  make promptfoo-eval
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from eval.helpers import threshold
from eval.metrics_registry import PROMPTFOO_METRICS
from eval.reporting import ReportCollector

PROMPTFOO_DIR = Path("promptfoo")
CONFIG = PROMPTFOO_DIR / "promptfooconfig.yaml"
OUTPUT = PROMPTFOO_DIR / "output.json"
GENERATOR = Path("scripts/generate_promptfoo_tests.py")


def _ensure_tests_generated() -> None:
    subprocess.run([sys.executable, str(GENERATOR)], check=True)


def _run_promptfoo() -> dict:
    _ensure_tests_generated()
    OUTPUT.unlink(missing_ok=True)
    cmd = [
        "npx",
        "--yes",
        "promptfoo@latest",
        "eval",
        "-c",
        str(CONFIG),
        "-o",
        str(OUTPUT),
    ]
    subprocess.run(cmd, check=True)
    return json.loads(OUTPUT.read_text())


def _parse_stats(data: dict) -> dict[str, float | int]:
    stats = (data.get("results") or {}).get("stats") or {}
    successes = int(stats.get("successes", 0))
    failures = int(stats.get("failures", 0))
    total = successes + failures
    pass_rate = (successes / total) if total else 0.0
    return {
        "pass_rate": pass_rate,
        "passed": successes,
        "total": total,
        "failed": failures,
    }


@pytest.mark.eval
@pytest.mark.slow
def test_promptfoo_full_suite():
    try:
        data = _run_promptfoo()
    except FileNotFoundError:
        pytest.skip("npx not available — install Node.js to run promptfoo")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"promptfoo eval failed (exit {e.returncode})")

    metrics = _parse_stats(data)
    for name in PROMPTFOO_METRICS:
        ReportCollector.set(f"promptfoo.{name}", metrics[name])

    floor = threshold("promptfoo.pass_rate", 0.75)
    assert metrics["pass_rate"] >= floor, (
        f"promptfoo pass_rate {metrics['pass_rate']:.3f} < {floor}\n"
        f"passed={metrics['passed']} failed={metrics['failed']} total={metrics['total']}"
    )
