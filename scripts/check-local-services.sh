#!/usr/bin/env bash
set -euo pipefail

check_get() {
  local name="$1"
  local url="$2"
  printf "%-12s %s\n" "$name" "$url"
  curl --max-time 3 --fail --silent --show-error "$url" >/dev/null \
    && echo "  ok" \
    || echo "  unavailable"
}

check_post_json() {
  local name="$1"
  local url="$2"
  local payload="$3"
  printf "%-12s %s\n" "$name" "$url"
  curl --max-time 10 --fail --silent --show-error \
    --request POST \
    --url "$url" \
    --header "Content-Type: application/json" \
    --data "$payload" >/dev/null \
    && echo "  ok" \
    || echo "  unavailable"
}

check_get "backend" "http://127.0.0.1:3301/health"
check_get "embedding" "http://127.0.0.1:8010/health"
check_post_json "reranker" "http://127.0.0.1:8020/rerank" '{"query":"health check","documents":[{"id":"health","text":"health check"}],"top_n":1}'
check_get "llm" "http://127.0.0.1:8040/v1/models"
check_get "qwen" "http://127.0.0.1:8030/v1/models"

printf "%-12s %s\n" "milvus" "http://127.0.0.1:19530/v2/vectordb/collections/list"
curl --max-time 3 --fail --silent --show-error \
  --request POST \
  --url "http://127.0.0.1:19530/v2/vectordb/collections/list" \
  --header "Content-Type: application/json" \
  --data '{"dbName":"default"}' >/dev/null \
  && echo "  ok" \
  || echo "  unavailable"
