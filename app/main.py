"""FastAPI service exposing the RAG pipeline and the agent."""
from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, field_validator

from app.agent import run_agent
from app.guards import validate_question
from app.providers import ProviderName
from app.rag import answer, collection_chunk_count
from app.retrieval.config import RetrievalMode, get_retrieval_mode

load_dotenv()
app = FastAPI(title="AI Compliance QA Lab")


class QueryIn(BaseModel):
    question: str
    provider: ProviderName = "anthropic"
    k: int = 5
    retrieval_mode: RetrievalMode | None = None

    @field_validator("question")
    @classmethod
    def check_question(cls, v: str) -> str:
        return validate_question(v)


class ChunkOut(BaseModel):
    text: str
    source: str
    distance: float


class QueryOut(BaseModel):
    answer: str
    chunks: list[ChunkOut]
    input_tokens: int
    output_tokens: int
    model: str
    provider: str
    retrieval_mode: str


class AgentIn(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def check_question(cls, v: str) -> str:
        return validate_question(v)


class AgentStepOut(BaseModel):
    step: int
    type: str
    tool_name: str | None = None
    tool_input: dict | None = None
    text: str | None = None
    error: str | None = None


class AgentOut(BaseModel):
    answer: str
    trajectory: list[AgentStepOut]
    steps_taken: int
    stopped_reason: str
    input_tokens: int
    output_tokens: int


@app.get("/health")
def health() -> dict:
    chunks = collection_chunk_count()
    status = "ok" if chunks > 0 else "degraded"
    return {
        "status": status,
        "corpus_chunks": chunks,
        "retrieval_mode": get_retrieval_mode().value,
        "message": "ready" if chunks > 0 else "run: python scripts/ingest_corpus.py",
    }


@app.post("/query", response_model=QueryOut)
def query(q: QueryIn) -> QueryOut:
    mode = q.retrieval_mode or get_retrieval_mode()
    r = answer(q.question, provider=q.provider, k=q.k, mode=mode)
    return QueryOut(
        answer=r.answer,
        chunks=[ChunkOut(text=c.text, source=c.source, distance=c.distance) for c in r.chunks],
        input_tokens=r.input_tokens,
        output_tokens=r.output_tokens,
        model=r.model,
        provider=r.provider,
        retrieval_mode=r.retrieval_mode,
    )


@app.post("/agent", response_model=AgentOut)
def agent(q: AgentIn) -> AgentOut:
    run = run_agent(q.question)
    return AgentOut(
        answer=run.final_answer,
        trajectory=[
            AgentStepOut(
                step=s.step,
                type=s.type,
                tool_name=s.tool_name,
                tool_input=s.tool_input,
                text=s.text,
                error=s.error,
            )
            for s in run.trajectory
        ],
        steps_taken=run.steps_taken,
        stopped_reason=run.stopped_reason,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
    )
