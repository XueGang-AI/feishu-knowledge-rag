# Feishu Knowledge RAG

本项目目标是构建一个完全本地优先的飞书知识库 RAG 系统：同步飞书知识库空间、节点、云文档与正文 block，将文档解析为可检索文本 chunk，使用本地 bge-m3 生成 embedding，写入本地 Milvus，查询时经 Milvus 召回和 bge-reranker-v2-m3 重排，再由 Qwen3.6-27B-GGUF 的 Q4_K_M 量化文件生成带来源引用的答案。

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
  -> Qwen3.6-27B Q4_K_M 生成答案
  -> 返回答案和来源引用
```

## 本机判断结论

| 项目 | 本机状态 | 处理方式 |
|------|----------|----------|
| bge-m3 | 已存在 `/Users/xuegang/Desktop/My Project/bge-m3-local` 和 Hugging Face 缓存 | 作为通用 embedding 服务复用，默认访问 `8010` |
| Milvus | 由通用 Milvus 服务提供，地址 `127.0.0.1:19530` | 本项目默认只连接，不自动启动 |
| bge-reranker-v2-m3 | 未发现本地缓存 | 下载 `BAAI/bge-reranker-v2-m3`，部署为 rerank 服务 |
| Qwen3.6-27B-GGUF | 未发现 GGUF 文件 | 下载 `Qwen3.6-27B-Q4_K_M.gguf` |
| llama.cpp | 未发现 `llama-server`/`llama-cli` | 安装或编译 llama.cpp，用 OpenAI-compatible API 部署 Qwen |
| Ollama / LM Studio | 未发现本地目录 | 不作为首选部署方式 |

关键判断：`Qwen3.6-27B-GGUF` 是 Hugging Face 仓库名，`Q4_K_M` 是具体量化档位，本项目配置应写为“仓库 `lmstudio-community/Qwen3.6-27B-GGUF`，文件 `Qwen3.6-27B-Q4_K_M.gguf`”。

详见 [docs/local-model-audit.md](docs/local-model-audit.md)。

## 推荐服务端口

| 服务 | 地址 |
|------|------|
| Backend FastAPI | `http://127.0.0.1:3301` |
| Frontend Next.js | `http://127.0.0.1:3300` |
| 通用 Embedding | `http://127.0.0.1:8010` |
| 通用 Reranker | `http://127.0.0.1:8020` |
| 通用 LLM | `http://127.0.0.1:8030/v1` |
| Milvus | `127.0.0.1:19530` |

## 来源追溯字段

Milvus 中每条 chunk 至少保留：

```text
chunk_id
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

## 后端开发启动

```bash
uv sync --extra dev
cp .env.example .env
./scripts/dev-backend.sh
```

## 本地模型服务

本项目的前端和后端启动脚本不会自动启动 Milvus、BGE、Reranker 或 Qwen。下面脚本只作为手动维护通用服务时使用。

```bash
# 下载 reranker 和 Qwen GGUF
./scripts/download-models.sh

# 启动 bge-m3 embedding，复用本机已有工程
./scripts/start-bge-m3.sh

# 启动 bge-reranker-v2-m3
./scripts/start-reranker.sh

# 安装 llama.cpp 后启动 Qwen3.6-27B Q4_K_M
./scripts/install-llamacpp-macos.sh
./scripts/start-qwen-llamacpp.sh
```

基础校验：

```bash
uv run pytest -q
uv run ruff check .
curl http://127.0.0.1:3301/health
```

当前已实现后端基础骨架、SQLite 状态库初始化、飞书同步任务框架、文档解析切块、Milvus 索引客户端、检索、重排、问答和来源查看 API。

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

`deploy/milvus/docker-compose.yml` 只作为可选隔离环境，默认宿主机端口为 `19310/19191/19100/19101/11888`，不会占用通用 Milvus 端口 `19530`。

## 文档

- [docs/local-model-audit.md](docs/local-model-audit.md)：本机模型、服务和部署方式判断。
- [docs/technical-solution.md](docs/technical-solution.md)：完整技术方案。
- [docs/development-plan.md](docs/development-plan.md)：按阶段拆解的开发计划。

## 参考链接

- [飞书知识库节点 API](https://open.feishu.cn/document/server-docs/docs/wiki-v2/space-node/get_node?lang=zh-CN)
- [飞书云文档说明](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/docx-overview?lang=zh-CN)
- [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)
- [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- [lmstudio-community/Qwen3.6-27B-GGUF](https://huggingface.co/lmstudio-community/Qwen3.6-27B-GGUF)
- [Milvus Docs](https://milvus.io/docs)
