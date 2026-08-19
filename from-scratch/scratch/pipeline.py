"""PDF/text → pages → chunks → Chroma. Loaded only by `make ingest`.

Unit tests never import Chroma or sentence-transformers. Those live
behind function-level imports so `make learn-s2` stays fast and free.
"""
from __future__ import annotations

import os
from pathlib import Path

from scratch.chunking import pages_to_chunks
from scratch.embeddings import get_embedding_model_name, get_embedding_provider
from scratch.ingest import CORPUS_DIR, IngestError, resolve_corpus_path

DEFAULT_FILE = CORPUS_DIR / "sample_policy.txt"


def chroma_path() -> Path:
    return Path(os.getenv("CHROMA_PATH", str(Path(__file__).resolve().parents[1] / "chroma_db")))


def collection_name() -> str:
    return os.getenv("COLLECTION_NAME", "sample_policy")


def load_pages(path: Path) -> list[tuple[int, str]]:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise IngestError(f"Corpus file is empty: {path}")
        return [(1, text)]
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages: list[tuple[int, str]] = []
        for i, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append((i + 1, text))
        if not pages:
            raise IngestError(f"PDF has no extractable text: {path}")
        return pages
    raise IngestError(f"Unsupported suffix: {path.suffix}")


def write_chroma(ids: list[str], documents: list[str], metadatas: list[dict]) -> int:
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    get_embedding_provider()
    embed_fn = SentenceTransformerEmbeddingFunction(
        model_name=get_embedding_model_name(),
        device=os.getenv("EMBEDDING_DEVICE", "cpu"),
        normalize_embeddings=True,
    )
    client = chromadb.PersistentClient(path=str(chroma_path()))
    name = collection_name()
    try:
        client.delete_collection(name)
    except Exception:
        pass
    coll = client.create_collection(
        name=name,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine", "embedding_model": get_embedding_model_name()},
    )
    coll.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(documents)


def ingest(raw: str | Path = DEFAULT_FILE) -> int:
    path = resolve_corpus_path(raw)
    pages = load_pages(path)
    ids, documents, metadatas = pages_to_chunks(pages)
    count = write_chroma(ids, documents, metadatas)
    print(f"Loaded {len(pages)} page(s) from {path.name}")
    print(f"Split into {count} chunks")
    print(f"Collection {collection_name()!r} @ {chroma_path()}")
    return count


def search_chunks(question: str, k: int = 4) -> list[dict]:
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    from scratch.guards import validate_question

    q = validate_question(question)
    embed_fn = SentenceTransformerEmbeddingFunction(
        model_name=get_embedding_model_name(),
        device=os.getenv("EMBEDDING_DEVICE", "cpu"),
        normalize_embeddings=True,
    )
    client = chromadb.PersistentClient(path=str(chroma_path()))
    name = collection_name()
    try:
        coll = client.get_collection(name=name, embedding_function=embed_fn)
    except Exception as exc:
        raise IngestError(f"Collection {name!r} not found. Run `make ingest` first. ({exc})") from exc
    result = coll.query(query_texts=[q], n_results=k)
    hits: list[dict] = []
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]
    ids = (result.get("ids") or [[]])[0]
    for i, doc in enumerate(docs):
        hits.append(
            {
                "id": ids[i] if i < len(ids) else None,
                "text": doc,
                "metadata": metas[i] if i < len(metas) else {},
                "distance": dists[i] if i < len(dists) else None,
            }
        )
    return hits


def main() -> int:
    try:
        ingest()
    except IngestError as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0
