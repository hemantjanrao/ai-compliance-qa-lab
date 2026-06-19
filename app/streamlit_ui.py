"""Streamlit UI — RAG + Agent + eval scorecard for demos and study."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from app.agent import run_agent
from app.env_check import (
    anthropic_configured,
    default_llm_provider,
    format_api_error,
    openai_configured,
    provider_status,
)
from app.rag import answer, collection_chunk_count
from app.retrieval.config import RetrievalMode, get_retrieval_mode

REPORT_PATH = Path("eval/reports/current.json")
BASELINE_PATH = Path("eval/reports/baseline.json")

st.set_page_config(page_title="EU AI Act QA Lab", layout="wide")
st.title("EU AI Act — AI QA Study Lab")

# --- API key status banner ---
status = provider_status()
if not anthropic_configured() and not openai_configured():
    st.error(
        "No LLM API keys configured. Copy `.env.example` → `.env` and add real keys.\n\n"
        f"- Anthropic: {status['anthropic']}\n"
        f"- OpenAI: {status['openai']}"
    )
elif not anthropic_configured():
    st.warning(f"Anthropic: {status['anthropic']}")
elif not openai_configured():
    st.warning(f"OpenAI: {status['openai']}")

tab_rag, tab_agent, tab_eval = st.tabs(["RAG Q&A", "Compliance Agent", "Eval Scorecard"])

with tab_rag:
    with st.sidebar:
        providers = []
        if anthropic_configured():
            providers.append("anthropic")
        if openai_configured():
            providers.append("openai")
        if not providers:
            providers = ["anthropic", "openai"]  # show UI; errors handled on submit

        default_idx = providers.index(default_llm_provider()) if default_llm_provider() in providers else 0
        provider = st.selectbox("Provider", providers, index=default_idx, key="rag_provider")
        retrieval_mode = st.selectbox(
            "Retrieval mode",
            ["advanced", "basic"],
            index=0 if get_retrieval_mode() == RetrievalMode.ADVANCED else 1,
            key="rag_retrieval_mode",
            help="Advanced: hybrid BM25 + vector fusion + cross-encoder rerank",
        )
        k = st.slider("Retrieved chunks (k)", 1, 10, 5, key="rag_k")

    chunks = collection_chunk_count()
    if chunks == 0:
        st.warning("Corpus not ingested. Run: `make ingest`")
    else:
        st.caption(f"Corpus: {chunks} chunks indexed")

    question = st.text_input(
        "Question",
        "What are the requirements for high-risk AI systems?",
        key="rag_q",
    )
    if st.button("Ask (RAG)", key="rag_ask"):
        if provider == "anthropic" and not anthropic_configured():
            st.error(f"Cannot use Anthropic: {status['anthropic']}")
        elif provider == "openai" and not openai_configured():
            st.error(f"Cannot use OpenAI: {status['openai']}")
        else:
            try:
                with st.spinner("Retrieving and generating..."):
                    mode = RetrievalMode(retrieval_mode)
                    result = answer(question, provider=provider, k=k, mode=mode)
                st.subheader("Answer")
                st.write(result.answer)
                st.caption(
                    f"Model: {result.model} | Retrieval: {result.retrieval_mode} | "
                    f"In: {result.input_tokens} tok | Out: {result.output_tokens} tok"
                )
                with st.expander("Retrieved chunks"):
                    for i, c in enumerate(result.chunks):
                        st.markdown(f"**Chunk {i+1}** — {c.source} (dist={c.distance:.3f})")
                        st.text(c.text[:500])
            except Exception as e:
                st.error(format_api_error(e))

with tab_agent:
    st.caption("ReAct agent with 4 tools — watch the trajectory, not just the answer.")
    if not anthropic_configured():
        st.warning(
            f"Agent requires a valid **Anthropic** key. Current status: {status['anthropic']}"
        )
    agent_q = st.text_input(
        "Agent question",
        "What is the maximum fine for prohibited AI practices?",
        key="agent_q",
    )
    if st.button("Run Agent", key="agent_run"):
        if not anthropic_configured():
            st.error(f"Cannot run agent: {status['anthropic']}")
        else:
            try:
                with st.spinner("Agent running..."):
                    run = run_agent(agent_q)
                st.subheader("Final answer")
                st.write(run.final_answer)
                st.caption(
                    f"Steps: {run.steps_taken} | Stopped: {run.stopped_reason} | "
                    f"Tokens in/out: {run.input_tokens}/{run.output_tokens}"
                )
                st.subheader("Trajectory")
                for s in run.trajectory:
                    if s.type == "text":
                        st.markdown(f"**Step {s.step} — reasoning**")
                        st.write(s.text)
                    elif s.type == "tool_use":
                        st.markdown(f"**Step {s.step} — tool `{s.tool_name}`**")
                        st.json(s.tool_input)
                    elif s.type == "error":
                        st.error(f"Step {s.step} — {s.tool_name}: {s.error}")
            except Exception as e:
                st.error(format_api_error(e))

with tab_eval:
    st.markdown(
        "Study view: compare your last eval run (`current.json`) against the baseline. "
        "Run locally with `make eval` or `make eval-full`."
    )
    for label, path in [("Current", REPORT_PATH), ("Baseline", BASELINE_PATH)]:
        st.subheader(label)
        if path.exists():
            data = json.loads(path.read_text())
            st.json(data)
            ragas = data.get("ragas", {})
            if ragas:
                for prov, metrics in ragas.items():
                    if metrics:
                        cols = st.columns(len(metrics))
                        for col, (metric_key, v) in zip(cols, metrics.items()):
                            col.metric(
                                f"{prov}.{metric_key}",
                                f"{v:.3f}" if isinstance(v, float) else v,
                            )
        else:
            st.info(f"No report at `{path}` yet.")
