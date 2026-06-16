"""RAGAS judge LLM + embeddings — explicit config avoids broken defaults.

RAGAS metrics use an LLM-as-judge internally. Without explicit llm/embeddings,
ragas 0.3 picks a broken InstructorLLM default (agenerate_prompt missing).

Study note: your app's LLM (answer generation) and RAGAS's judge LLM are
separate calls — both need API keys via .env.
"""
from __future__ import annotations

import os

from langchain_anthropic import ChatAnthropic
from langchain_community.embeddings import HuggingFaceEmbeddings
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper


def get_ragas_llm() -> LangchainLLMWrapper:
    """Judge LLM for RAGAS metrics — uses Anthropic Haiku (cheap)."""
    return LangchainLLMWrapper(
        ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            temperature=0,
            max_tokens=4096,
        )
    )


def get_ragas_embeddings() -> LangchainEmbeddingsWrapper:
    """Local embeddings for RAGAS — matches app EMBEDDING_PROVIDER=local."""
    model = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    return LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(
            model_name=model,
            model_kwargs={"device": os.getenv("EMBEDDING_DEVICE", "cpu")},
            encode_kwargs={"normalize_embeddings": True},
        )
    )
