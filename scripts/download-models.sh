#!/usr/bin/env bash
set -euo pipefail

GEMMA_DIR="${GEMMA_DIR:-/Users/xuegang/models/gemma-4-12b-it-qat-q4_0-gguf}"
QWEN_DIR="${QWEN_DIR:-/Users/xuegang/models/qwen3.6-27b-gguf}"
DOWNLOAD_QWEN="${DOWNLOAD_QWEN:-false}"

if ! command -v uvx >/dev/null 2>&1; then
  echo "uvx is required. Install uv first." >&2
  exit 1
fi

echo "Downloading BAAI/bge-reranker-v2-m3 to Hugging Face cache..."
uvx --from huggingface_hub huggingface-cli download BAAI/bge-reranker-v2-m3

echo "Downloading Gemma 4 12B IT QAT Q4_0 GGUF to $GEMMA_DIR..."
mkdir -p "$GEMMA_DIR"
uvx --from huggingface_hub huggingface-cli download \
  google/gemma-4-12B-it-qat-q4_0-gguf \
  gemma-4-12b-it-qat-q4_0.gguf \
  --local-dir "$GEMMA_DIR"

if [ "$DOWNLOAD_QWEN" = "true" ]; then
  echo "Downloading Qwen3.6-27B Q4_K_M GGUF to $QWEN_DIR..."
  mkdir -p "$QWEN_DIR"
  uvx --from huggingface_hub huggingface-cli download \
    lmstudio-community/Qwen3.6-27B-GGUF \
    Qwen3.6-27B-Q4_K_M.gguf \
    --local-dir "$QWEN_DIR"
fi

echo "Done."
