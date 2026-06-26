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
| bge-m3 | 已存在 `/Users/xuegang/Desktop/My Project/bge-m3-local` 和 Hugging Face 缓存 | 作为 embedding 服务复用，建议改用 `8002` 端口启动 |
| Milvus | 已有 Docker 镜像和容器，但 standalone/etcd/minio 当前未运行 | 修复或迁移 compose 后启动，保留 `19530` |
| bge-reranker-v2-m3 | 未发现本地缓存 | 下载 `BAAI/bge-reranker-v2-m3`，部署为 rerank 服务 |
| Qwen3.6-27B-GGUF | 未发现 GGUF 文件 | 下载 `Qwen3.6-27B-Q4_K_M.gguf` |
| llama.cpp | 未发现 `llama-server`/`llama-cli` | 安装或编译 llama.cpp，用 OpenAI-compatible API 部署 Qwen |
| Ollama / LM Studio | 未发现本地目录 | 不作为首选部署方式 |

关键判断：`Qwen3.6-27B-GGUF` 是 Hugging Face 仓库名，`Q4_K_M` 是具体量化档位，本项目配置应写为“仓库 `lmstudio-community/Qwen3.6-27B-GGUF`，文件 `Qwen3.6-27B-Q4_K_M.gguf`”。

详见 [docs/local-model-audit.md](docs/local-model-audit.md)。

## 推荐服务端口

| 服务 | 地址 |
|------|------|
| Backend FastAPI | `http://127.0.0.1:8080` |
| Frontend Next.js | `http://127.0.0.1:3001` |
| bge-m3 embedding | `http://127.0.0.1:8002` |
| bge-reranker-v2-m3 | `http://127.0.0.1:8003` |
| llama.cpp / Qwen | `http://127.0.0.1:8004/v1` |
| Milvus | `127.0.0.1:19530` |
| Attu | `http://127.0.0.1:8000` |

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
| `GET /api/sync/status` | 查看整体同步状态 |
| `POST /api/reindex` | 按空间、节点或文档重新索引 |
| `POST /api/search` | 返回召回和重排后的 chunk |
| `POST /api/chat` | 返回答案和来源引用 |

## 后端开发启动

```bash
uv sync --extra dev
cp .env.example .env
./scripts/dev-backend.sh
```

如果 `8080` 已被占用，可临时使用：

```bash
APP_PORT=8081 ./scripts/dev-backend.sh
```

基础校验：

```bash
uv run pytest -q
uv run ruff check .
curl http://127.0.0.1:8080/health
```

当前已实现后端基础骨架、SQLite 状态库初始化、`/health`、`POST /api/sync/jobs`、`GET /api/sync/jobs`、`GET /api/sync/jobs/{job_id}` 和 `GET /api/sync/status`。飞书真实同步、切块、Milvus upsert、rerank 和 chat 会按 `docs/development-plan.md` 后续阶段接入。

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
