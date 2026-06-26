#!/usr/bin/env bash
set -euo pipefail

QWEN_DIR="${QWEN_DIR:-/Users/xuegang/models/qwen3.6-27b-gguf}"

if ! command -v uvx >/dev/null 2>&1; then
  echo "uvx is required. Install uv first." >&2
  exit 1
fi

echo "Downloading BAAI/bge-reranker-v2-m3 to Hugging Face cache..."
uvx --from huggingface_hub huggingface-cli download BAAI/bge-reranker-v2-m3

echo "Downloading Qwen3.6-27B Q4_K_M GGUF to $QWEN_DIR..."
mkdir -p "$QWEN_DIR"
uvx --from huggingface_hub huggingface-cli download \
  lmstudio-community/Qwen3.6-27B-GGUF \
  Qwen3.6-27B-Q4_K_M.gguf \
  --local-dir "$QWEN_DIR"

echo "Done."
