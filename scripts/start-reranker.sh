#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="${RERANKER_SERVICE_DIR:-/Users/xuegang/Desktop/My Project/Model/bge-reranker-service}"

if [ ! -x "$SERVICE_DIR/scripts/start.sh" ]; then
  echo "Reranker service wrapper not found: $SERVICE_DIR/scripts/start.sh" >&2
  echo "Set RERANKER_SERVICE_DIR to override the default service directory." >&2
  exit 1
fi

exec "$SERVICE_DIR/scripts/start.sh"
