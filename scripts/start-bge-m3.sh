#!/usr/bin/env bash
set -euo pipefail

BGE_M3_PROJECT_DIR="${BGE_M3_PROJECT_DIR:-/Users/xuegang/Desktop/My Project/bge-m3-local}"
BGE_PORT="${BGE_PORT:-8002}"
BGE_DEVICE="${BGE_DEVICE:-mps}"

if [ ! -x "$BGE_M3_PROJECT_DIR/scripts/start.sh" ]; then
  echo "bge-m3 start script not found: $BGE_M3_PROJECT_DIR/scripts/start.sh" >&2
  exit 1
fi

cd "$BGE_M3_PROJECT_DIR"
BGE_PORT="$BGE_PORT" ./scripts/start.sh "$BGE_DEVICE"
