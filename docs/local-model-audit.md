# 本机模型与部署判断

审计时间：2026-06-27，时区：Asia/Shanghai。模型服务拆分状态更新：2026-07-01。

## 结论

你当前机器上可以直接复用的是 `Model/` 下的 bge-m3 embedding、bge-reranker-v2-m3、Qwen llama.cpp、Gemma llama.cpp 服务工程，以及通用 Milvus Docker 服务。

| 能力 | 目标模型/组件 | 本机发现 | 当前状态 | 部署判断 |
|------|---------------|----------|----------|----------|
| Embedding | `BAAI/bge-m3` | `/Users/xuegang/Desktop/My Project/Model/bge-m3-service`，模型入口 `/Users/xuegang/models/bge-m3` | 权重存在，服务是否运行由通用服务管理 | 本项目默认连接 `8010`，不自动启动 |
| Vector DB | Milvus standalone | Docker 镜像 `milvusdb/milvus:v2.6.18`、`quay.io/coreos/etcd:v3.5.25`、`minio/minio`、`zilliz/attu:v2.6.3` | 通用 Milvus 由外部管理 | 本项目默认连接 `19530`，不自动启动 |
| Rerank | `BAAI/bge-reranker-v2-m3` | `/Users/xuegang/Desktop/My Project/Model/bge-reranker-service`，模型入口 `/Users/xuegang/models/bge-reranker-v2-m3` | 权重存在，服务由通用服务管理，默认 CPU 推理 | 本项目默认连接 `8020`，不自动承载 |
| Generation | `google/gemma-4-12B-it-qat-q4_0-gguf` | `/Users/xuegang/Desktop/My Project/Model/gemma-4-12b-llamacpp-service`，GGUF 文件 `/Users/xuegang/models/gemma-4-12b-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf` | 权重存在，服务由通用服务管理 | 本项目默认连接 `8040/v1`，不自动承载 |
| Generation Fallback / Comparison | `lmstudio-community/Qwen3.6-27B-GGUF` | `/Users/xuegang/Desktop/My Project/Model/qwen-llamacpp-service`，GGUF 文件 `/Users/xuegang/models/qwen3.6-27b-gguf/Qwen3.6-27B-Q4_K_M.gguf` | 权重存在，服务由通用服务管理 | 可选回退/对比时连接 `8030/v1`，不自动承载 |
| Inference Server | llama.cpp | `llama-server` 用于 Gemma 和 Qwen 通用服务 | 已有通用封装 | 提供 OpenAI-compatible API |

## 已确认的本地文件与服务

### bge-m3

本机已有：

```text
/Users/xuegang/Desktop/My Project/Model/bge-m3-service
/Users/xuegang/.cache/huggingface/hub/models--BAAI--bge-m3
```

现有 bge-m3 项目说明：

- 使用官方 `BAAI/bge-m3`。
- 使用 `FlagEmbedding`。
- `use_fp16=False`。
- dense 输出维度为 1024。
- 支持 OpenAI-style `POST /v1/embeddings`。
- 支持原生 `POST /v1/bge-m3/encode`，可返回 dense、sparse、ColBERT。
- 本项目期望通用服务端口为 `8010`。

当前状态：

- 服务运行状态以 `http://127.0.0.1:8010/health` 为准。
- 本项目不再依赖旧的本地专用端口，统一连接通用 Embedding 服务。

建议启动方式：

```bash
cd "/Users/xuegang/Desktop/My Project/Model/bge-m3-service"
BGE_PORT=8010 ./scripts/start.sh mps
curl http://127.0.0.1:8010/info
```

本项目后端配置：

```env
EMBEDDING_BASE_URL=http://127.0.0.1:8010
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
```

### Milvus

本机已有 Docker 镜像：

```text
milvusdb/milvus:v2.6.18
quay.io/coreos/etcd:v3.5.25
minio/minio:RELEASE.2024-05-28T17-19-04Z
zilliz/attu:v2.6.3
```

当前状态：

- Milvus 由通用 Docker 服务管理，本项目不默认启动。
- 本项目健康检查通过 Milvus API `127.0.0.1:19530` 判断可用性。
- 运行状态以如下 health check 为准：

```bash
curl --request POST http://127.0.0.1:19530/v2/vectordb/collections/list \
  --header "Content-Type: application/json" \
  --data '{"dbName":"default"}'
```

本项目后端配置：

```env
MILVUS_URI=http://127.0.0.1:19530
MILVUS_DB=default
MILVUS_COLLECTION=feishu_chunks_v2
MILVUS_LEGACY_COLLECTION=feishu_chunks_v1
```

### bge-reranker-v2-m3

本机当前使用：

```text
/Users/xuegang/Desktop/My Project/Model/bge-reranker-service
/Users/xuegang/models/bge-reranker-v2-m3
```

推荐启动方式：

```bash
cd "/Users/xuegang/Desktop/My Project/Model/bge-reranker-service"
./scripts/start.sh
curl --max-time 10 -sf \
  --request POST \
  --url http://127.0.0.1:8020/rerank \
  --header "Content-Type: application/json" \
  --data '{"query":"health check","documents":[{"id":"health","text":"health check"}],"top_n":1}'
```

默认使用 `RERANKER_DEVICE=cpu`，避免 FlagEmbedding 在本机自动选设备时出现 `Cannot copy out of meta tensor`。如需实验其他设备，可显式设置 `RERANKER_DEVICE=auto` 或具体设备值后再启动。

Feishu RAG 兼容 wrapper：

```bash
./scripts/start-reranker.sh
```

建议接口：

```http
POST http://127.0.0.1:8020/rerank
```

请求：

```json
{
  "query": "如何申请知识库权限？",
  "documents": [
    {"id": "chunk_1", "text": "......"}
  ],
  "top_n": 8
}
```

响应：

```json
{
  "results": [
    {"id": "chunk_1", "score": 0.91, "rank": 1}
  ]
}
```

### Qwen3.6-27B-GGUF Q4_K_M（可选回退/对比）

本机当前使用：

```text
/Users/xuegang/Desktop/My Project/Model/qwen-llamacpp-service
/Users/xuegang/models/qwen3.6-27b-gguf/Qwen3.6-27B-Q4_K_M.gguf
```

注意：`Qwen3.6-27B-GGUF` 是仓库名，`Q4_K_M` 是具体量化档位。项目配置不要把 `Q4_K_M` 写成模型名。

推荐启动方式：

```bash
cd "/Users/xuegang/Desktop/My Project/Model/qwen-llamacpp-service"
./scripts/start.sh
curl -sf http://127.0.0.1:8030/v1/models
```

Feishu RAG 兼容 wrapper：

```bash
./scripts/start-qwen-llamacpp.sh
```

可选回退/对比配置：

```env
LLM_BASE_URL=http://127.0.0.1:8030/v1
LLM_MODEL=Qwen3.6-27B-GGUF:Q4_K_M
LLM_CONTEXT_SIZE=32768
```

### Gemma 4 12B IT QAT Q4_0 GGUF（默认生成模型）

本机默认生成服务使用：

```text
/Users/xuegang/Desktop/My Project/Model/gemma-4-12b-llamacpp-service
/Users/xuegang/models/gemma-4-12b-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf
```

仓库：

```text
google/gemma-4-12B-it-qat-q4_0-gguf
```

主文件：

```text
gemma-4-12b-it-qat-q4_0.gguf
```

可选多模态投影文件：

```text
mmproj-gemma-4-12b-it-qat-q4_0.gguf
```

推荐启动方式：

```bash
cd "/Users/xuegang/Desktop/My Project/Model/gemma-4-12b-llamacpp-service"
./scripts/start.sh
curl -sf http://127.0.0.1:8040/v1/models
```

Feishu RAG 兼容 wrapper：

```bash
./scripts/start-gemma-llamacpp.sh
```

本项目后端默认配置：

```env
LLM_BASE_URL=http://127.0.0.1:8040/v1
LLM_MODEL=gemma-4-12b-it-qat-q4_0
LLM_CONTEXT_SIZE=32768
```

## 推荐部署顺序

1. 确认通用 Milvus：先保证 `19530` 可用。
2. 确认通用 Embedding：使用 `8010`，验证 `/v1/embeddings`。
3. 确认通用 Reranker：使用 `8020`，验证 query-document score。
4. 确认通用 Gemma LLM：使用 `8040/v1`，验证 chat completion。
5. 如需回退/对比，再确认通用 Qwen LLM：使用 `8030/v1`，验证 chat completion。
6. 启动本项目 backend：使用 `3301`，串联 embedding、Milvus、reranker、LLM。
7. 启动 frontend：使用 `3300`。

## 需要写入项目配置的模型字段

```env
EMBEDDING_PROVIDER=bge-m3-service
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_BASE_URL=http://127.0.0.1:8010
EMBEDDING_DIM=1024

RERANKER_PROVIDER=bge-reranker-local
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_BASE_URL=http://127.0.0.1:8020

LLM_PROVIDER=llama.cpp
LLM_MODEL_REPO=google/gemma-4-12B-it-qat-q4_0-gguf
LLM_MODEL_FILE=gemma-4-12b-it-qat-q4_0.gguf
LLM_MODEL=gemma-4-12b-it-qat-q4_0
LLM_BASE_URL=http://127.0.0.1:8040/v1

# Optional Qwen 27B fallback/comparison:
# LLM_MODEL_REPO=lmstudio-community/Qwen3.6-27B-GGUF
# LLM_MODEL_FILE=Qwen3.6-27B-Q4_K_M.gguf
# LLM_MODEL=Qwen3.6-27B-GGUF:Q4_K_M
# LLM_BASE_URL=http://127.0.0.1:8030/v1

MILVUS_URI=http://127.0.0.1:19530
MILVUS_COLLECTION=feishu_chunks_v2
MILVUS_LEGACY_COLLECTION=feishu_chunks_v1
```
