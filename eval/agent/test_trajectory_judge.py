"""Trajectory quality eval — backward-compatible entry point.

Full agent DeepEval suite: eval/agent/test_deepeval_agent.py

Run:
  pytest eval/agent/test_trajectory_judge.py -v -m eval
"""
from __future__ import annotations

import pytest

from eval.agent.trajectory_utils import TRAJECTORY_TEST_QUESTIONS, trajectory_to_text  # noqa: F401


@pytest.mark.eval
@pytest.mark.slow
def test_trajectory_quality():
    from eval.agent.test_deepeval_agent import test_trajectory_quality as _run

    _run()
