#!/usr/bin/env bash
# Copy Session 2 ingest/search into the standalone ai-qa-from-scratch repo.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-}"

if [[ -z "$DEST" ]]; then
  echo "Usage: bash install-into.sh /path/to/ai-qa-from-scratch"
  echo "Example: bash install-into.sh \$HOME/files/ai-qa-from-scratch"
  exit 1
fi

DEST="$(cd "$DEST" && pwd)"
if [[ ! -f "$DEST/app/guards.py" ]]; then
  echo "ERROR: $DEST does not look like ai-qa-from-scratch (missing app/guards.py)"
  exit 1
fi

mkdir -p "$DEST/app" "$DEST/scripts" "$DEST/corpus" "$DEST/tests"
cp "$SRC/Makefile" "$DEST/Makefile"
cp "$SRC/pyproject.toml" "$DEST/pyproject.toml"
cp "$SRC/.env.example" "$DEST/.env.example"
cp "$SRC/app/ingest.py" "$DEST/app/ingest.py"
cp "$SRC/app/chunking.py" "$DEST/app/chunking.py"
cp "$SRC/app/embeddings.py" "$DEST/app/embeddings.py"
cp "$SRC/app/pipeline.py" "$DEST/app/pipeline.py"
cp "$SRC/app/rag.py" "$DEST/app/rag.py"
cp "$SRC/scripts/ingest_corpus.py" "$DEST/scripts/ingest_corpus.py"
cp "$SRC/scripts/search_chunks.py" "$DEST/scripts/search_chunks.py"
cp "$SRC/scripts/ask.py" "$DEST/scripts/ask.py"
cp "$SRC/corpus/sample_policy.txt" "$DEST/corpus/sample_policy.txt"
mkdir -p "$DEST/tests"
cp "$SRC/tests/test_rag.py" "$DEST/tests/test_rag.py"

# Keep Session 1 secrets file; append Session 2 keys if missing
if [[ -f "$DEST/.env" ]] && ! grep -q 'EMBEDDING_PROVIDER' "$DEST/.env"; then
  cat >> "$DEST/.env" << 'EOF'

EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2
CHROMA_PATH=./chroma_db
COLLECTION_NAME=sample_policy
CHUNK_SIZE=2000
CHUNK_OVERLAP=100
MAX_ARTICLE=20
EOF
fi

echo "Installed Session 2–3 into $DEST"
echo "Next:"
echo "  cd $DEST"
echo "  make setup"
echo "  make unit"
echo "  make ingest"
echo "  make search Q=\"What is prohibited under Article 5?\""
echo "  make ask Q=\"What is prohibited under Article 5?\""
