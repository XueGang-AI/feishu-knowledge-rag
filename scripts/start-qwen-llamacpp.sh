#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${QWEN_GGUF_PATH:-/Users/xuegang/models/qwen3.6-27b-gguf/Qwen3.6-27B-Q4_K_M.gguf}"
HOST="${LLM_HOST:-127.0.0.1}"
PORT="${LLM_PORT:-8030}"
CTX_SIZE="${LLM_CTX_SIZE:-32768}"
PARALLEL="${LLM_PARALLEL:-1}"
LLAMA_SERVER_BIN="${LLAMA_SERVER_BIN:-llama-server}"

if ! command -v "$LLAMA_SERVER_BIN" >/dev/null 2>&1; then
  echo "llama-server not found. Run ./scripts/install-llamacpp-macos.sh first." >&2
  exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
  echo "Qwen GGUF file not found: $MODEL_PATH" >&2
  echo "Run ./scripts/download-models.sh first or set QWEN_GGUF_PATH." >&2
  exit 1
fi

"$LLAMA_SERVER_BIN" \
  -m "$MODEL_PATH" \
  --host "$HOST" \
  --port "$PORT" \
  --ctx-size "$CTX_SIZE" \
  --jinja \
  --parallel "$PARALLEL"
