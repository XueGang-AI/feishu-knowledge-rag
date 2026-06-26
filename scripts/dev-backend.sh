#!/usr/bin/env bash
set -euo pipefail

HOST="${APP_HOST:-127.0.0.1}"
PORT="${APP_PORT:-8080}"

python -m uvicorn backend.app.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --reload
