"""Ingest the EU AI Act PDF into ChromaDB.

Download the official Regulation (EU) 2024/1689 from:
  https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689
Save it as corpus/eu_ai_act.pdf, then run:
  python scripts/ingest_corpus.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import chromadb

from app.embeddings import get_chroma_embedding_function, get_embedding_provider
from app.retrieval.bm25_index import BM25Index
from app.retrieval.config import bm25_index_path

load_dotenv()

CORPUS_DIR = Path("corpus")
PDF_PATH = CORPUS_DIR / "eu_ai_act.pdf"
_ARTICLE_RE = re.compile(r"\bArticle\s+(\d{1,3})\b")


def _chunk_metadata(page_content: str, page: int) -> dict:
    meta: dict = {"source": f"page_{page}", "page": page}
    match = _ARTICLE_RE.search(page_content)
    if match:
        article = int(match.group(1))
        if 1 <= article <= 113:
            meta["article"] = article
    return meta


def main() -> int:
    if not PDF_PATH.exists():
        print(f"ERROR: {PDF_PATH} not found.")
        print("Download from https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689")
        return 1

    print(f"Loading {PDF_PATH}...")
    docs = PyPDFLoader(str(PDF_PATH)).load()
    print(f"Loaded {len(docs)} pages")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=100,
        separators=["\nArticle ", "\nChapter ", "\n\n", "\n", ". ", " "],
    )
    chunks = splitter.split_documents(docs)
    print(f"Split into {len(chunks)} chunks")

    provider = get_embedding_provider()
    print(f"Embedding provider: {provider}")

    client = chromadb.PersistentClient(path=os.getenv("CHROMA_PATH", "./chroma_db"))
    embed_fn = get_chroma_embedding_function()
    name = os.getenv("COLLECTION_NAME", "eu_ai_act")
    try:
        client.delete_collection(name)
    except Exception:
        pass
    coll = client.create_collection(name=name, embedding_function=embed_fn)

    ids = [f"chunk_{i}" for i in range(len(chunks))]
    documents = [c.page_content for c in chunks]
    metadatas = [_chunk_metadata(c.page_content, c.metadata.get("page", 0)) for c in chunks]

    coll.add(ids=ids, documents=documents, metadatas=metadatas)

    bm25 = BM25Index.from_records(ids=ids, documents=documents, metadatas=metadatas)
    index_path = bm25_index_path()
    bm25.save(index_path)
    print(f"Ingested {len(chunks)} chunks into '{name}' collection.")
    print(f"BM25 index saved to {index_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
