# Feishu Knowledge RAG

本项目目标是构建一个完全本地优先的飞书知识库 RAG 系统：同步飞书知识库空间、节点、云文档与正文 block，将文档解析为可检索文本 chunk，使用本地 bge-m3 生成 embedding，写入本地 Milvus，查询时经 Milvus 召回和 bge-reranker-v2-m3 重排，再由通用 OpenAI-compatible LLM 服务生成带来源引用的答案。默认生成模型为 Gemma 4 12B IT QAT Q4_0 GGUF；Qwen3.6-27B-GGUF Q4_K_M 保留为可选回退/对比模型。

## 核心链路

```text
飞书知识库
  -> 飞书 API 拉取知识空间 / 节点 / 文档 / block
  -> 文档清洗与结构化
  -> 按标题层级和语义边界切 chunk
  -> bge-m3 生成 embedding
  -> Milvus 存储向量和 metadata
  -> 用户提问
  -> bge-m3 生成 query embedding
  -> Milvus 召回 top 50
  -> bge-reranker-v2-m3 重排 top 5-8
  -> 拼接上下文和来源信息
  -> Gemma 4 12B Q4_0 默认生成答案，可切换 Qwen3.6-27B Q4_K_M 对比
  -> 返回答案和来源引用
```

## 通用服务依赖

| 能力 | 地址 | 说明 |
|------|------|------|
| Embedding | `http://127.0.0.1:8010` | `/Users/xuegang/Desktop/My Project/Model/bge-m3-service` |
| Reranker | `http://127.0.0.1:8020` | `/Users/xuegang/Desktop/My Project/Model/bge-reranker-service` |
| LLM | `http://127.0.0.1:8040/v1` | `/Users/xuegang/Desktop/My Project/Model/gemma-4-12b-llamacpp-service` |
| Qwen LLM（可选/回退/对比） | `http://127.0.0.1:8030/v1` | `/Users/xuegang/Desktop/My Project/Model/qwen-llamacpp-service` |
| Milvus | `http://127.0.0.1:19530` | 通用 Milvus 服务 |

关键判断：`Qwen3.6-27B-GGUF` 是 Hugging Face 仓库名，`Q4_K_M` 是具体量化档位，本项目配置应写为“仓库 `lmstudio-community/Qwen3.6-27B-GGUF`，文件 `Qwen3.6-27B-Q4_K_M.gguf`”。

详见 [docs/local-model-audit.md](docs/local-model-audit.md)。

通用模型服务工程统一放在 `/Users/xuegang/Desktop/My Project/Model/`，模型权重统一放在 `/Users/xuegang/models/`。本项目只保留兼容启动 wrapper：

```bash
./scripts/start-bge-m3.sh
./scripts/start-reranker.sh
./scripts/start-qwen-llamacpp.sh
./scripts/start-gemma-llamacpp.sh
```

这些 wrapper 默认调用 `Model/` 下的通用服务；可用 `BGE_M3_PROJECT_DIR`、`RERANKER_SERVICE_DIR`、`QWEN_LLAMACPP_SERVICE_DIR`、`GEMMA_LLAMACPP_SERVICE_DIR` 覆盖服务工程路径。

`./scripts/download-models.sh` 默认下载 bge-reranker-v2-m3 与 Gemma 主 GGUF；如需同时下载 Qwen 对比模型，使用 `DOWNLOAD_QWEN=true ./scripts/download-models.sh`。

## Gemma 默认与 Qwen 可选

默认使用 Gemma 4 12B IT QAT Q4_0：

```env
LLM_BASE_URL=http://127.0.0.1:8040/v1
LLM_MODEL=gemma-4-12b-it-qat-q4_0
```

切换 Qwen 27B 回退/对比：

```env
LLM_BASE_URL=http://127.0.0.1:8030/v1
LLM_MODEL=Qwen3.6-27B-GGUF:Q4_K_M
```

## 推荐服务端口

| 服务 | 地址 |
|------|------|
| Backend FastAPI | `http://127.0.0.1:3301` |
| Frontend Next.js | `http://127.0.0.1:3300` |
| 通用 Embedding | `http://127.0.0.1:8010` |
| 通用 Reranker | `http://127.0.0.1:8020` |
| 通用 LLM（Gemma 默认） | `http://127.0.0.1:8040/v1` |
| 通用 Qwen LLM（可选/回退/对比） | `http://127.0.0.1:8030/v1` |
| Milvus | `127.0.0.1:19530` |

## 来源追溯字段

Milvus 中每条 chunk 至少保留：

```text
chunk_id
account_id
space_id
node_token
doc_token
doc_type
title
section_path
source_url
block_ids
content
content_hash
updated_time
embedding
```

本地 SQLite 还应保存同步任务、文档版本、block hash、chunk hash、索引状态和错误原因，支持增量同步、重新索引、删除同步和状态查看。
当前主 collection 为 `feishu_chunks_v2`；`feishu_chunks_v1` 仅作为旧数据 fallback collection。

## API 目标

| API | 用途 |
|-----|------|
| `POST /api/sync/jobs` | 创建同步任务 |
| `GET /api/sync/jobs/{job_id}` | 查看同步任务详情 |
| `POST /api/sync/jobs/{job_id}/run` | 启动已创建的同步任务 |
| `POST /api/sync/jobs/{job_id}/cancel` | 取消待运行或运行中的同步任务 |
| `GET /api/sync/status` | 查看整体同步状态 |
| `POST /api/reindex` | 按空间、节点或文档重新索引 |
| `POST /api/search` | 返回召回和重排后的 chunk |
| `POST /api/chat` | 返回答案和来源引用 |
| `GET /api/sources/{chunk_id}` | 查看来源 chunk 详情 |

`POST /api/search` 和 `POST /api/chat` 支持 `account_id`、`space_id`、`doc_token` 过滤。`POST /api/chat` 支持 `mode=auto|direct|rag`：普通问题默认 direct；涉及飞书知识库、文档范围或开启强制检索时走 RAG。文档级重新索引的 `scope_id` 必须使用 `space_id:node_token`，而文档内问答检索过滤使用 `doc_token`。

## 后端开发启动

```bash
uv sync --extra dev
cp .env.example .env
./scripts/dev-backend.sh
```

基础校验：

```bash
uv run pytest -q
uv run ruff check .
curl http://127.0.0.1:3301/health
```

当前已实现后端基础骨架、SQLite 状态库初始化、多飞书账号同步任务框架、文档解析切块、Milvus 索引客户端、检索、重排、自动/直接/RAG 问答、来源查看、weekly scan 和同步状态 API。
如果 Reranker 推理接口不可用，`/api/search` 和 RAG 问答会降级使用 Milvus 原始召回结果继续返回，此时结果中的 `rerank_score` 为 `null`，`/health` 会把 `reranker` 标记为不可用。

## 前端开发启动

```bash
cd frontend
cp .env.example .env
pnpm install
pnpm dev
```

默认前端地址：

```text
http://127.0.0.1:3300
```

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:3301
```

前端校验：

```bash
pnpm --dir frontend lint
pnpm --dir frontend build
```

注意：不要在同一个 `frontend/.next` 目录上同时跑 `next dev` 和 `next build`。如果已经在 `3300` 开着 dev server，先停止 dev server 再 build，或 build 后重启 dev server，避免浏览器加载旧 chunk 出现 Next runtime overlay。

`deploy/milvus/docker-compose.yml` 只作为可选隔离环境，不参与本项目默认启动流程。
`deploy/reranker/` 仅保留为历史兼容目录；新的通用 Reranker 服务入口在 `/Users/xuegang/Desktop/My Project/Model/bge-reranker-service`。

## 文档

- [docs/local-model-audit.md](docs/local-model-audit.md)：本机模型、服务和部署方式判断。
- [docs/model-service-split-brief.md](docs/model-service-split-brief.md)：通用模型服务拆分记录。
- [docs/technical-solution.md](docs/technical-solution.md)：完整技术方案。
- [docs/development-plan.md](docs/development-plan.md)：按阶段拆解的开发计划。

## 参考链接

- [飞书知识库节点 API](https://open.feishu.cn/document/server-docs/docs/wiki-v2/space-node/get_node?lang=zh-CN)
- [飞书云文档说明](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/docx-overview?lang=zh-CN)
- [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)
- [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- [lmstudio-community/Qwen3.6-27B-GGUF](https://huggingface.co/lmstudio-community/Qwen3.6-27B-GGUF)
- [google/gemma-4-12B-it-qat-q4_0-gguf](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf)
- [Milvus Docs](https://milvus.io/docs)
