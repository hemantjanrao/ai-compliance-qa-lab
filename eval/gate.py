"""Eval gate — compare current run metrics against baseline.

Study note: this is the production pattern interviewers ask about:
  1. Run eval harness → produce artifact (current.json)
  2. Compare to last-known-good baseline
  3. Block merge if regression exceeds tolerance

Usage:
  python -m eval.gate                          # compare current vs baseline
  python -m eval.gate --promote                # copy current → baseline (main only)
  python -m eval.gate --baseline path.json --current path.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eval.reporting import BASELINE_REPORT, CURRENT_REPORT, load_thresholds

RAGAS_METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
DEEPEVAL_PROVIDER_METRICS = ("citation_correctness", "refusal_correctness")
DEEPEVAL_AGENT_METRICS = ("trajectory_quality",)
PROVIDERS = ("anthropic", "openai")


@dataclass
class GateFailure:
    check: str
    message: str


@dataclass
class GateResult:
    passed: bool
    failures: list[GateFailure] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Report not found: {path}")
    return json.loads(path.read_text())


def _metric_drop(baseline: float, current: float) -> float:
    return baseline - current


def _latency_increase(baseline: float, current: float) -> float:
    if baseline <= 0:
        return 0.0
    return (current - baseline) / baseline


def compare_reports(
    baseline: dict[str, Any],
    current: dict[str, Any],
    *,
    max_metric_drop: float | None = None,
    max_latency_increase: float | None = None,
) -> GateResult:
    thresholds = load_thresholds().get("gate", {})
    max_metric_drop = max_metric_drop if max_metric_drop is not None else thresholds.get("max_metric_drop", 0.05)
    max_latency_increase = (
        max_latency_increase
        if max_latency_increase is not None
        else thresholds.get("max_latency_increase", 0.30)
    )

    result = GateResult(passed=True)
    ragas_floor = load_thresholds().get("ragas", {})
    deepeval_floor = load_thresholds().get("deepeval", {})

    # --- RAGAS: absolute floors ---
    for provider in PROVIDERS:
        for metric in RAGAS_METRICS:
            value = (current.get("ragas") or {}).get(provider, {}).get(metric)
            floor = ragas_floor.get(metric)
            if value is None or floor is None:
                result.warnings.append(f"Skipping floor check: ragas.{provider}.{metric} (missing data)")
                continue
            if value < floor:
                result.passed = False
                result.failures.append(
                    GateFailure(
                        check=f"floor.ragas.{provider}.{metric}",
                        message=f"{metric}={value:.3f} below floor {floor:.3f}",
                    )
                )

    # --- RAGAS: regression vs baseline ---
    for provider in PROVIDERS:
        base_p = (baseline.get("ragas") or {}).get(provider, {})
        cur_p = (current.get("ragas") or {}).get(provider, {})
        for metric in RAGAS_METRICS:
            b, c = base_p.get(metric), cur_p.get(metric)
            if b is None or c is None:
                result.warnings.append(f"Skipping regression: ragas.{provider}.{metric} (missing baseline or current)")
                continue
            drop = _metric_drop(b, c)
            if drop > max_metric_drop:
                result.passed = False
                result.failures.append(
                    GateFailure(
                        check=f"regression.ragas.{provider}.{metric}",
                        message=f"{metric} dropped {drop:.3f} ({b:.3f} → {c:.3f}), limit {max_metric_drop:.3f}",
                    )
                )

    # --- DeepEval: absolute floors (per provider) ---
    for provider in PROVIDERS:
        for metric in DEEPEVAL_PROVIDER_METRICS:
            value = (current.get("deepeval") or {}).get(provider, {}).get(metric)
            floor = deepeval_floor.get(metric)
            if value is None or floor is None:
                result.warnings.append(f"Skipping floor check: deepeval.{provider}.{metric} (missing data)")
                continue
            if value < floor:
                result.passed = False
                result.failures.append(
                    GateFailure(
                        check=f"floor.deepeval.{provider}.{metric}",
                        message=f"{metric}={value:.3f} below floor {floor:.3f}",
                    )
                )

    # --- DeepEval: absolute floors (agent metrics) ---
    for metric in DEEPEVAL_AGENT_METRICS:
        value = (current.get("deepeval") or {}).get(metric)
        floor = deepeval_floor.get(metric)
        if value is None or floor is None:
            result.warnings.append(f"Skipping floor check: deepeval.{metric} (missing data)")
            continue
        if value < floor:
            result.passed = False
            result.failures.append(
                GateFailure(
                    check=f"floor.deepeval.{metric}",
                    message=f"{metric}={value:.3f} below floor {floor:.3f}",
                )
            )

    # --- DeepEval: regression vs baseline (per provider) ---
    for provider in PROVIDERS:
        base_p = (baseline.get("deepeval") or {}).get(provider, {})
        cur_p = (current.get("deepeval") or {}).get(provider, {})
        for metric in DEEPEVAL_PROVIDER_METRICS:
            b, c = base_p.get(metric), cur_p.get(metric)
            if b is None or c is None:
                result.warnings.append(
                    f"Skipping regression: deepeval.{provider}.{metric} (missing baseline or current)"
                )
                continue
            drop = _metric_drop(b, c)
            if drop > max_metric_drop:
                result.passed = False
                result.failures.append(
                    GateFailure(
                        check=f"regression.deepeval.{provider}.{metric}",
                        message=f"{metric} dropped {drop:.3f} ({b:.3f} → {c:.3f}), limit {max_metric_drop:.3f}",
                    )
                )

    # --- DeepEval: regression vs baseline (agent metrics) ---
    for metric in DEEPEVAL_AGENT_METRICS:
        b = (baseline.get("deepeval") or {}).get(metric)
        c = (current.get("deepeval") or {}).get(metric)
        if b is None or c is None:
            result.warnings.append(f"Skipping regression: deepeval.{metric} (missing baseline or current)")
            continue
        drop = _metric_drop(b, c)
        if drop > max_metric_drop:
            result.passed = False
            result.failures.append(
                GateFailure(
                    check=f"regression.deepeval.{metric}",
                    message=f"{metric} dropped {drop:.3f} ({b:.3f} → {c:.3f}), limit {max_metric_drop:.3f}",
                )
            )

    # --- Latency p95 regression ---
    base_lat = baseline.get("latency_p95_ms") or {}
    cur_lat = current.get("latency_p95_ms") or {}
    for provider in PROVIDERS:
        b, c = base_lat.get(provider), cur_lat.get(provider)
        if b is None or c is None:
            continue
        inc = _latency_increase(b, c)
        if inc > max_latency_increase:
            result.passed = False
            result.failures.append(
                GateFailure(
                    check=f"regression.latency.{provider}",
                    message=f"p95 latency up {inc:.1%} ({b:.0f}ms → {c:.0f}ms), limit {max_latency_increase:.1%}",
                )
            )

    # --- Adversarial must stay passing ---
    for suite in ("rag_passed", "agent_passed"):
        if baseline.get("adversarial", {}).get(suite) is True:
            if current.get("adversarial", {}).get(suite) is not True:
                result.passed = False
                result.failures.append(
                    GateFailure(
                        check=f"adversarial.{suite}",
                        message=f"Adversarial suite {suite} was passing on baseline but not on current run",
                    )
                )

    return result


def format_gate_summary(result: GateResult, baseline: dict, current: dict) -> str:
    lines = ["# Eval Gate Report", ""]
    lines.append(f"**Baseline commit:** {baseline.get('commit', '?')}")
    lines.append(f"**Current commit:** {current.get('commit', '?')}")
    lines.append(f"**Result:** {'PASS' if result.passed else 'FAIL'}")
    lines.append("")

    if result.failures:
        lines.append("## Failures")
        for f in result.failures:
            lines.append(f"- `{f.check}`: {f.message}")
        lines.append("")

    lines.append("## RAGAS scores")
    for provider in PROVIDERS:
        cur = (current.get("ragas") or {}).get(provider, {})
        base = (baseline.get("ragas") or {}).get(provider, {})
        if cur:
            parts = [f"{m}={cur.get(m, '?'):.3f}" for m in RAGAS_METRICS if cur.get(m) is not None]
            base_parts = [f"{m}={base.get(m, '?'):.3f}" for m in RAGAS_METRICS if base.get(m) is not None]
            lines.append(f"- **{provider}** current: {', '.join(parts)}")
            if base_parts:
                lines.append(f"  baseline: {', '.join(base_parts)}")
    lines.append("")

    deepeval = current.get("deepeval") or {}
    if deepeval:
        lines.append("## DeepEval scores")
        for provider in PROVIDERS:
            cur = deepeval.get(provider, {})
            if cur:
                parts = [f"{m}={cur.get(m, '?'):.3f}" for m in DEEPEVAL_PROVIDER_METRICS if cur.get(m) is not None]
                if parts:
                    lines.append(f"- **{provider}** {', '.join(parts)}")
        for metric in DEEPEVAL_AGENT_METRICS:
            if deepeval.get(metric) is not None:
                lines.append(f"- **agent** {metric}={deepeval[metric]:.3f}")
        lines.append("")

    if result.warnings:
        lines.append("## Warnings")
        for w in result.warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval gate — baseline comparison")
    parser.add_argument("--baseline", type=Path, default=BASELINE_REPORT)
    parser.add_argument("--current", type=Path, default=CURRENT_REPORT)
    parser.add_argument("--promote", action="store_true", help="Copy current report to baseline")
    parser.add_argument("--markdown", type=Path, help="Write markdown summary to file")
    args = parser.parse_args(argv)

    if args.promote:
        if not args.current.exists():
            print(f"ERROR: no current report at {args.current}", file=sys.stderr)
            return 1
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(args.current, args.baseline)
        print(f"Promoted {args.current} → {args.baseline}")
        return 0

    baseline = _load_json(args.baseline)
    current = _load_json(args.current)
    result = compare_reports(baseline, current)
    summary = format_gate_summary(result, baseline, current)
    print(summary)

    if args.markdown:
        args.markdown.write_text(summary + "\n")

    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
