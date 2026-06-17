"""Streamlit UI E2E — requires running app.

Run:
  make serve          # terminal 1
  E2E_UI=1 make e2e-ui   # terminal 2 (needs: playwright install chromium)
"""
from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(os.getenv("E2E_UI") != "1", reason="Set E2E_UI=1 and run make serve first"),
]


@pytest.fixture
def streamlit_url() -> str:
    return os.getenv("STREAMLIT_URL", "http://localhost:8501")


def test_streamlit_home_loads(page, streamlit_url: str):
    page.goto(streamlit_url, wait_until="networkidle", timeout=30_000)
    assert page.locator("body").inner_text()
