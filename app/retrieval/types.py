"""Shared retrieval types."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    text: str
    source: str
    distance: float
