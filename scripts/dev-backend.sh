#!/usr/bin/env bash
set -euo pipefail

HOST="${APP_HOST:-127.0.0.1}"
PORT="${APP_PORT:-3301}"

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON="python3.11"
else
  PYTHON="python3"
fi

"$PYTHON" -m uvicorn backend.app.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --reload
