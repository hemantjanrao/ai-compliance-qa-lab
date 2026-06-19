"""DeepEval agent metrics — trajectory, tool correctness, task completion.

Run:
  pytest eval/agent/test_deepeval_agent.py -v -m eval
"""
from __future__ import annotations

import json

import pytest
from deepeval.metrics import GEval, TaskCompletionMetric, ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase, LLMTestCaseParams, ToolCall

from app.agent import run_agent
from eval.agent.trajectory_utils import TRAJECTORY_TEST_QUESTIONS, trajectory_to_text
from eval.conftest import load_cached_agent_run, save_cached_agent_run
from eval.helpers import load_golden_agent, threshold
from eval.metrics_registry import DEEPEVAL_AGENT_METRICS
from eval.reporting import ReportCollector

trajectory_metric = GEval(
    name="TrajectoryQuality",
    criteria=(
        "Evaluate the agent's trajectory for the given question. A good trajectory: "
        "(1) calls the right tool(s) for the task, "
        "(2) does not call unnecessary tools, "
        "(3) does not retry the same call without changing args, "
        "(4) reaches the answer in as few steps as reasonable. "
        "The actual output contains both the trajectory log and the final answer."
    ),
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.7,
)


def _tool_calls_from_run(run) -> list[ToolCall]:
    return [
        ToolCall(name=s.tool_name, input_parameters=s.tool_input or {})
        for s in run.trajectory
        if s.type == "tool_use" and s.tool_name
    ]


@pytest.mark.eval
@pytest.mark.slow
def test_trajectory_quality():
    floor = threshold("deepeval.trajectory_quality", 0.70)
    scores: list[float] = []
    for question in TRAJECTORY_TEST_QUESTIONS:
        run = run_agent(question)
        actual = f"TRAJECTORY:\n{trajectory_to_text(run)}\n\nFINAL ANSWER:\n{run.final_answer}"
        tc = LLMTestCase(input=question, actual_output=actual)
        trajectory_metric.measure(tc)
        scores.append(trajectory_metric.score)
        assert trajectory_metric.score >= floor, (
            f"Trajectory score {trajectory_metric.score} < {floor}\n"
            f"Reason: {trajectory_metric.reason}"
        )
    ReportCollector.set("deepeval.trajectory_quality", sum(scores) / len(scores))


def _cached_run(case: dict, agent_cache_dir):
    question = case["question"]
    case_id = case.get("id", "")
    run = load_cached_agent_run(question, agent_cache_dir, case_id=case_id)
    if run is None:
        run = run_agent(question)
        save_cached_agent_run(run, agent_cache_dir, case_id=case_id)
    return run


@pytest.mark.eval
@pytest.mark.slow
def test_tool_correctness_suite(agent_cache_dir):
    """DeepEval ToolCorrectnessMetric — mean score over golden agent cases."""
    cases = [
        c for c in load_golden_agent()
        if "expected_tools" in c or "expected_tools_any_of" in c
    ]
    if not cases:
        pytest.skip("No tool-selection golden cases")

    metric = ToolCorrectnessMetric(threshold=0.7, async_mode=False)
    floor = threshold("deepeval.tool_correctness", 0.70)
    scores: list[float] = []

    for case in cases:
        run = _cached_run(case, agent_cache_dir)
        expected = case.get("expected_tools")
        if expected is None:
            expected = case["expected_tools_any_of"][0]

        tc = LLMTestCase(
            input=case["question"],
            actual_output=run.final_answer,
            tools_called=_tool_calls_from_run(run),
            expected_tools=[ToolCall(name=n) for n in expected],
        )
        metric.measure(tc)
        scores.append(metric.score)
        assert metric.score >= floor, (
            f"Tool correctness failed for {case['id']}: {metric.score}\n"
            f"Called: {run.tool_names_called()}, Expected: {expected}"
        )

    ReportCollector.set("deepeval.tool_correctness", sum(scores) / len(scores))


@pytest.mark.eval
@pytest.mark.slow
def test_task_completion_suite(agent_cache_dir):
    """DeepEval TaskCompletionMetric — mean score over all golden agent cases."""
    cases = load_golden_agent()
    metric = TaskCompletionMetric(threshold=0.7, async_mode=False)
    floor = threshold("deepeval.task_completion", 0.70)
    scores: list[float] = []

    for case in cases:
        run = _cached_run(case, agent_cache_dir)
        tc = LLMTestCase(
            input=case["question"],
            actual_output=run.final_answer,
            tools_called=_tool_calls_from_run(run),
        )
        metric.measure(tc)
        scores.append(metric.score)
        assert metric.score >= floor, (
            f"Task completion failed for {case['id']}: {metric.score}\n"
            f"Reason: {getattr(metric, 'reason', '')}"
        )

    ReportCollector.set("deepeval.task_completion", sum(scores) / len(scores))


@pytest.mark.eval
def test_agent_metrics_registered():
    assert "trajectory_quality" in DEEPEVAL_AGENT_METRICS
