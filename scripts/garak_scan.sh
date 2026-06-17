#!/usr/bin/env bash
# Automated red-team scan via garak (optional — install: pip install garak)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

if ! command -v garak &>/dev/null; then
  echo "Installing garak into .venv..."
  pip install -q garak
fi

PROVIDER="${GARAK_MODEL_TYPE:-litellm}"
MODEL="${GARAK_MODEL_NAME:-anthropic/claude-3-haiku-20240307}"
PROBES="${GARAK_PROBES:-promptinject,dan,encoding}"
GENERATIONS="${GARAK_GENERATIONS:-3}"

echo "Running garak: provider=$PROVIDER model=$MODEL probes=$PROBES"
garak --model_type "$PROVIDER" \
  --model_name "$MODEL" \
  --probes "$PROBES" \
  --generations "$GENERATIONS"
