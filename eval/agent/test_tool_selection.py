"""Agent tool-selection accuracy and trajectory correctness.

Tests:
- Right tool picked for each task class
- No hallucinated tool calls
- No infinite loops
- Adversarial: prompt injection doesn't hijack tool selection

Run:
  pytest eval/agent/test_tool_selection.py -v -m eval
"""
from __future__ import annotations

import json
from collections import Counter

import pytest

from eval.helpers import load_golden_agent

CASES = load_golden_agent()


@pytest.mark.eval
@pytest.mark.parametrize("agent_run_for_case", CASES, indirect=True, ids=lambda c: c["id"])
def test_tool_selection(agent_run_for_case):
    case, run = agent_run_for_case
    called = run.tool_names_called()

    assert not run.has_tool_error() or "Article" in case["question"], (
        f"Unexpected tool error in trajectory:\n{run.trajectory}"
    )

    if "expected_tools" in case:
        for t in case["expected_tools"]:
            assert t in called, (
                f"Expected tool '{t}' not called.\nCalled: {called}\nQ: {case['question']}"
            )
    if "expected_tools_any_of" in case:
        ok = any(all(t in called for t in option) for option in case["expected_tools_any_of"])
        ok = ok or [] in case["expected_tools_any_of"]
        assert ok, (
            f"None of the acceptable tool sequences matched.\n"
            f"Called: {called}\nAcceptable: {case['expected_tools_any_of']}"
        )

    for t in case.get("forbidden_tools", []):
        assert t not in called, f"Forbidden tool '{t}' was called. Q: {case['question']}"


@pytest.mark.eval
@pytest.mark.parametrize("agent_run_for_case", CASES, indirect=True, ids=lambda c: c["id"])
def test_final_answer_content(agent_run_for_case):
    case, run = agent_run_for_case
    answer_lower = run.final_answer.lower()
    for needle in case.get("expected_in_answer", []):
        assert needle.lower() in answer_lower, (
            f"Expected '{needle}' in answer.\nAnswer: {run.final_answer}\nQ: {case['question']}"
        )
    for forbidden in case.get("must_not_contain", []):
        assert forbidden not in run.final_answer, (
            f"Forbidden text '{forbidden}' found.\nAnswer: {run.final_answer}"
        )


@pytest.mark.eval
@pytest.mark.parametrize("agent_run_for_case", CASES, indirect=True, ids=lambda c: c["id"])
def test_no_infinite_loops(agent_run_for_case):
    """Agent should not call the same tool with the same args more than 2 times."""
    case, run = agent_run_for_case
    signatures = [
        (s.tool_name, json.dumps(s.tool_input, sort_keys=True))
        for s in run.trajectory
        if s.type == "tool_use"
    ]
    counts = Counter(signatures)
    for sig, count in counts.items():
        assert count <= 2, (
            f"Loop detected: {sig} called {count} times in run for: {case['question']}"
        )


@pytest.mark.eval
def test_step_budget():
    """Agent should resolve typical questions within 5 steps."""
    from app.agent import run_agent

    over_budget = []
    for case in CASES:
        run = run_agent(case["question"])
        if run.steps_taken > 5:
            over_budget.append((case["id"], run.steps_taken))
    assert len(over_budget) <= 2, f"Too many cases exceed 5-step budget: {over_budget}"
