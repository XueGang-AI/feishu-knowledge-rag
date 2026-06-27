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

check_get "backend" "http://127.0.0.1:3301/health"
check_get "embedding" "http://127.0.0.1:8010/health"
check_get "reranker" "http://127.0.0.1:8020/health"
check_get "llm" "http://127.0.0.1:8030/v1/models"

printf "%-12s %s\n" "milvus" "http://127.0.0.1:19530/v2/vectordb/collections/list"
curl --max-time 3 --silent --show-error \
  --request POST \
  --url "http://127.0.0.1:19530/v2/vectordb/collections/list" \
  --header "Content-Type: application/json" \
  --data '{"dbName":"default"}' >/dev/null \
  && echo "  ok" \
  || echo "  unavailable"
