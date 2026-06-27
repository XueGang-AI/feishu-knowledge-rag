#!/usr/bin/env bash
set -euo pipefail

HOST="${RERANKER_HOST:-127.0.0.1}"
PORT="${RERANKER_PORT:-8020}"

cd "$(dirname "$0")/../deploy/reranker"
uv sync
uv run uvicorn app:app --host "$HOST" --port "$PORT"
