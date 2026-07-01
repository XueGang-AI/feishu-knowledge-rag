#!/usr/bin/env bash
set -euo pipefail

BGE_M3_PROJECT_DIR="${BGE_M3_PROJECT_DIR:-/Users/xuegang/Desktop/My Project/Model/bge-m3-service}"
BGE_PORT="${BGE_PORT:-8010}"
BGE_DEVICE="${BGE_DEVICE:-mps}"
BGE_HOST="${BGE_HOST:-127.0.0.1}"
BGE_UVICORN_WORKERS="${BGE_UVICORN_WORKERS:-1}"
BGE_LOG_LEVEL="${BGE_LOG_LEVEL:-info}"

if [ ! -x "$BGE_M3_PROJECT_DIR/.venv/bin/python" ]; then
  echo "bge-m3 Python runtime not found: $BGE_M3_PROJECT_DIR/.venv/bin/python" >&2
  echo "Run setup in the bge-m3 service directory first." >&2
  exit 1
fi

cd "$BGE_M3_PROJECT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export BGE_DEVICE="$BGE_DEVICE"
export BGE_USE_FP16="${BGE_USE_FP16:-false}"
export BGE_PORT="$BGE_PORT"

exec .venv/bin/python -m uvicorn app.main:app \
  --host "$BGE_HOST" \
  --port "$BGE_PORT" \
  --workers "$BGE_UVICORN_WORKERS" \
  --log-level "${BGE_LOG_LEVEL,,}"
