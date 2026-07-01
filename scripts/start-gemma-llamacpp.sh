#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="${GEMMA_LLAMACPP_SERVICE_DIR:-/Users/xuegang/Desktop/My Project/Model/gemma-4-12b-llamacpp-service}"

if [ ! -x "$SERVICE_DIR/scripts/start.sh" ]; then
  echo "Gemma llama.cpp service wrapper not found: $SERVICE_DIR/scripts/start.sh" >&2
  echo "Set GEMMA_LLAMACPP_SERVICE_DIR to override the default service directory." >&2
  exit 1
fi

exec "$SERVICE_DIR/scripts/start.sh"
