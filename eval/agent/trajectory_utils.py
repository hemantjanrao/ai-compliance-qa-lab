"""Shared trajectory formatting for agent DeepEval tests."""
from __future__ import annotations

import json

TRAJECTORY_TEST_QUESTIONS = [
    "What is the maximum fine for using prohibited AI?",
    "Look up Article 5.",
    "Is social scoring banned under the AI Act?",
    "What category does an AI hiring system fall into, and what fine could apply if non-compliant?",
]


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
