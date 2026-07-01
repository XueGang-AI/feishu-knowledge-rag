#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="${QWEN_LLAMACPP_SERVICE_DIR:-/Users/xuegang/Desktop/My Project/Model/qwen-llamacpp-service}"

if [ ! -x "$SERVICE_DIR/scripts/start.sh" ]; then
  echo "Qwen llama.cpp service wrapper not found: $SERVICE_DIR/scripts/start.sh" >&2
  echo "Set QWEN_LLAMACPP_SERVICE_DIR to override the default service directory." >&2
  exit 1
fi

exec "$SERVICE_DIR/scripts/start.sh"
