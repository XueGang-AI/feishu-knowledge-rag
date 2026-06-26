#!/usr/bin/env bash
set -euo pipefail

check_get() {
  local name="$1"
  local url="$2"
  printf "%-12s %s\n" "$name" "$url"
  curl --max-time 3 --silent --show-error "$url" >/dev/null \
    && echo "  ok" \
    || echo "  unavailable"
}

check_get "backend" "http://127.0.0.1:8080/health"
check_get "bge-m3" "http://127.0.0.1:8002/health"
check_get "reranker" "http://127.0.0.1:8003/health"
check_get "llm" "http://127.0.0.1:8004/v1/models"
check_get "milvus" "http://127.0.0.1:9091/healthz"
