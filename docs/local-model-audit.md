# 本机模型与部署判断

审计时间：2026-06-27，时区：Asia/Shanghai。

## 结论

你当前机器上可以直接复用的是 bge-m3 embedding 服务工程和 Milvus Docker 镜像/容器；需要新增部署的是 bge-reranker-v2-m3、Qwen3.6-27B-GGUF Q4_K_M 和 llama.cpp。

| 能力 | 目标模型/组件 | 本机发现 | 当前状态 | 部署判断 |
|------|---------------|----------|----------|----------|
| Embedding | `BAAI/bge-m3` | `/Users/xuegang/Desktop/My Project/bge-m3-local`，以及 HF 缓存 `/Users/xuegang/.cache/huggingface/hub/models--BAAI--bge-m3` | 权重存在，服务是否运行由通用服务管理 | 本项目默认连接 `8010`，不自动启动 |
| Vector DB | Milvus standalone | Docker 镜像 `milvusdb/milvus:v2.6.18`、`quay.io/coreos/etcd:v3.5.25`、`minio/minio`、`zilliz/attu:v2.6.3` | 通用 Milvus 由外部管理 | 本项目默认连接 `19530`，不自动启动 |
| Rerank | `BAAI/bge-reranker-v2-m3` | 未发现 HF 缓存 | 未部署 | 下载模型，部署 reranker 服务 |
| Generation | `lmstudio-community/Qwen3.6-27B-GGUF` | 未发现 `.gguf` 文件 | 未部署 | 下载 `Qwen3.6-27B-Q4_K_M.gguf` |
| Inference Server | llama.cpp | 未发现 `llama-server` / `llama-cli` | 未安装 | 安装或编译 llama.cpp，提供 OpenAI-compatible API |

## 已确认的本地文件与服务

### bge-m3

本机已有：

```text
/Users/xuegang/Desktop/My Project/bge-m3-local
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

当前问题：

- 服务未运行。
- 本项目不再依赖旧的本地专用端口，统一连接通用 Embedding 服务。

建议启动方式：

```bash
cd "/Users/xuegang/Desktop/My Project/bge-m3-local"
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

当前容器状态：

```text
milvus-standalone  Exited
milvus-etcd        Exited
milvus-minio       Exited
milvus-attu        由外部或隔离 compose 管理
```

当前发现的问题：

- Milvus API `127.0.0.1:19530` 不可连接。
- 本项目健康检查通过 Milvus API `127.0.0.1:19530` 判断可用性。
- 实际项目目录在 `/Users/xuegang/Desktop/milvus-local`。
- 现有脚本硬编码 `cd "$HOME/milvus-local"`，会失败。
- Docker inspect 显示部分旧容器 mount 曾指向 `/Users/xuegang/milvus-local/...`，与现有目录不一致。

建议处理：

1. 在本项目中新增可复现的 Milvus compose 配置，或修复 `/Users/xuegang/Desktop/milvus-local/scripts/*.sh` 的路径。
2. 确认数据目录统一为 `/Users/xuegang/Desktop/milvus-local/volumes` 或迁移到本项目 `deploy/milvus/volumes`。
3. 启动 `etcd`、`minio`、`standalone` 后验证：

```bash
docker compose -f "/Users/xuegang/Desktop/milvus-local/docker-compose.yml" up -d etcd minio standalone
curl --request POST http://127.0.0.1:19530/v2/vectordb/collections/list \
  --header "Content-Type: application/json" \
  --data '{"dbName":"default"}'
```

本项目后端配置：

```env
MILVUS_URI=http://127.0.0.1:19530
MILVUS_DB=default
MILVUS_COLLECTION=feishu_chunks_v1
```

### bge-reranker-v2-m3

本机未发现：

```text
models--BAAI--bge-reranker-v2-m3
```

需要下载：

```bash
huggingface-cli download BAAI/bge-reranker-v2-m3
```

推荐部署方式：

- 独立 FastAPI 服务，通用端口 `8020`。
- 后端通过 HTTP 调用 `/rerank`，输入 query 和候选 chunk，输出 score 排序。
- 优先尝试 MPS；若 PyTorch/MPS 不稳定，切换 CPU 小 batch。

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

### Qwen3.6-27B-GGUF Q4_K_M

本机未发现 `.gguf` 文件，也未发现 `~/.lmstudio` 或 `~/.ollama` 模型目录。

已确认目标 Hugging Face 仓库与文件名：

```text
repo: lmstudio-community/Qwen3.6-27B-GGUF
file: Qwen3.6-27B-Q4_K_M.gguf
```

注意：`Qwen3.6-27B-GGUF` 是仓库名，`Q4_K_M` 是具体量化档位。项目配置不要把 `Q4_K_M` 写成模型名。

推荐下载目录：

```text
/Users/xuegang/models/qwen3.6-27b-gguf/Qwen3.6-27B-Q4_K_M.gguf
```

推荐部署方式：

- 安装或编译 llama.cpp。
- 使用 `llama-server` 提供 OpenAI-compatible API。
- 服务端口建议 `8030`。

示例启动命令：

```bash
llama-server \
  -m "/Users/xuegang/models/qwen3.6-27b-gguf/Qwen3.6-27B-Q4_K_M.gguf" \
  --host 127.0.0.1 \
  --port 8030 \
  --ctx-size 32768 \
  --jinja \
  --parallel 1
```

本项目后端配置：

```env
LLM_BASE_URL=http://127.0.0.1:8030/v1
LLM_MODEL=Qwen3.6-27B-GGUF:Q4_K_M
LLM_CONTEXT_SIZE=32768
```

## 推荐部署顺序

1. 确认通用 Milvus：先保证 `19530` 可用。
2. 确认通用 Embedding：使用 `8010`，验证 `/v1/embeddings`。
3. 确认通用 Reranker：使用 `8020`，验证 query-document score。
4. 确认通用 LLM：使用 `8030/v1`，验证 chat completion。
5. 启动本项目 backend：使用 `3301`，串联 embedding、Milvus、reranker、LLM。
6. 启动 frontend：使用 `3300`。

## 需要写入项目配置的模型字段

```env
EMBEDDING_PROVIDER=bge-m3-local
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_BASE_URL=http://127.0.0.1:8010
EMBEDDING_DIM=1024

RERANKER_PROVIDER=bge-reranker-local
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_BASE_URL=http://127.0.0.1:8020

LLM_PROVIDER=llama.cpp
LLM_MODEL_REPO=lmstudio-community/Qwen3.6-27B-GGUF
LLM_MODEL_FILE=Qwen3.6-27B-Q4_K_M.gguf
LLM_MODEL=Qwen3.6-27B-GGUF:Q4_K_M
LLM_BASE_URL=http://127.0.0.1:8030/v1

MILVUS_URI=http://127.0.0.1:19530
MILVUS_COLLECTION=feishu_chunks_v1
```
