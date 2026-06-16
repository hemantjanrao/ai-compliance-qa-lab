"""Trajectory quality eval — uses LLM-as-judge to score the *reasoning path*, not just the answer.

This is what distinguishes agent QA from RAG QA: even a correct answer reached via a
bad trajectory (unnecessary tools, wrong order) is a regression signal.

Run:
  pytest eval/agent/test_trajectory_judge.py -v -m eval
"""
from __future__ import annotations

import json

import pytest
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from app.agent import run_agent
from eval.helpers import threshold


def trajectory_to_text(run) -> str:
    lines = []
    for s in run.trajectory:
        if s.type == "text":
            lines.append(f"[Reasoning]: {s.text[:300]}")
        elif s.type == "tool_use":
            lines.append(f"[Tool: {s.tool_name}] args={json.dumps(s.tool_input)}")
        elif s.type == "error":
            lines.append(f"[Error: {s.tool_name}] {s.error}")
    return "\n".join(lines)


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


TRAJECTORY_TEST_QUESTIONS = [
    "What is the maximum fine for using prohibited AI?",
    "Look up Article 5.",
    "Is social scoring banned under the AI Act?",
    "What category does an AI hiring system fall into, and what fine could apply if non-compliant?",
]


@pytest.mark.eval
@pytest.mark.slow
@pytest.mark.parametrize("question", TRAJECTORY_TEST_QUESTIONS)
def test_trajectory_quality(question: str):
    run = run_agent(question)
    actual = f"TRAJECTORY:\n{trajectory_to_text(run)}\n\nFINAL ANSWER:\n{run.final_answer}"
    tc = LLMTestCase(input=question, actual_output=actual)
    traj_threshold = threshold("deepeval.trajectory_quality", 0.70)
    trajectory_metric.measure(tc)
    assert trajectory_metric.score >= traj_threshold, (
        f"Trajectory score {trajectory_metric.score} < {traj_threshold}\n"
        f"Reason: {trajectory_metric.reason}\n"
        f"Trajectory:\n{trajectory_to_text(run)}"
    )
