"""API smoke tests — fast E2E without live LLM calls."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.guards import MAX_QUESTION_CHARS
from app.main import app

client = TestClient(app)


def test_health_endpoint_shape():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "corpus_chunks" in body
    assert "retrieval_mode" in body
    assert isinstance(body["corpus_chunks"], int)


def test_query_rejects_oversized_question():
    r = client.post("/query", json={"question": "x" * (MAX_QUESTION_CHARS + 1)})
    assert r.status_code == 422


def test_agent_rejects_empty_question():
    r = client.post("/agent", json={"question": "   "})
    assert r.status_code == 422
