# AGENTS.md

本仓库用于建设“飞书知识库本地 RAG”系统：从飞书知识库同步空间、节点、文档与正文 block，解析为可检索 chunk，使用本地 bge-m3、Milvus、bge-reranker-v2-m3 和 Qwen3.6-27B-GGUF Q4_K_M 完成本地问答，并返回可追溯来源。

## 当前约束

- 远程仓库：`git@github.com:XueGang-AI/feishu-knowledge-rag.git`
- 当前本地目录尚未初始化为 git 仓库，首次开发前需要 `git init` 或 clone 远程仓库。
- 不要提交飞书 app secret、tenant access token、用户 cookie、模型下载 token、Milvus 数据目录。
- 本阶段只沉淀文档与方案，不实现业务代码。

## 本机已确认环境

- bge-m3：已存在本地项目 `/Users/xuegang/Desktop/My Project/bge-m3-local`，已缓存 `BAAI/bge-m3` 权重，输出 dense 维度 1024。
- bge-m3 当前未运行，默认 8000 端口与 Attu 冲突。后续建议以 `BGE_PORT=8002 ./scripts/start.sh mps` 启动。
- Milvus：已有 Docker 镜像与容器，版本 `milvusdb/milvus:v2.6.18`；但 `milvus-standalone`、`milvus-etcd`、`milvus-minio` 当前未运行，只有 Attu 占用 `127.0.0.1:8000`。
- bge-reranker-v2-m3：本机未发现缓存，需要下载并部署。
- Qwen3.6-27B-GGUF：本机未发现 GGUF 文件，需要下载 `Qwen3.6-27B-Q4_K_M.gguf` 并用 llama.cpp 部署。
- llama.cpp：未发现 `llama-server` 或 `llama-cli`，需要安装或编译。

## 技术方向

- 后端：Python + FastAPI。
- 同步状态库：SQLite 优先，DuckDB 可用于后续分析和离线检查。
- 文档结构：以 JSON block AST 为主，Markdown 为可读中间表示。
- Embedding：调用本地 bge-m3 服务，优先 MPS。
- 向量库：本地 Milvus standalone，collection 维度 1024。
- Rerank：`BAAI/bge-reranker-v2-m3`，建议独立 FastAPI 服务或后端内嵌模块，先独立服务便于资源隔离。
- 生成：`llama.cpp` 的 OpenAI-compatible API，加载 `Qwen3.6-27B-Q4_K_M.gguf`。
- 前端：Next.js / React，端口建议 `3001`，避免已有 `3000/3002` 占用。

## 开发原则

- chunk 必须保留来源字段：`chunk_id`、`space_id`、`node_token`、`doc_token`、`doc_type`、`title`、`section_path`、`source_url`、`block_ids`、`content`、`content_hash`、`updated_time`。
- 回答必须返回来源引用，至少可追溯到飞书文档；可用时追溯到 block_id。
- 增量同步以飞书更新时间、block 内容 hash、本地文档 hash 三层判断为准。
- 检索链路固定为：query embedding -> Milvus top 50 -> rerank top 5-8 -> Qwen 生成 -> citations。
- 遇到飞书 API 限流、权限不足、文档删除、节点移动时，需要记录同步任务状态，不能静默丢失。

## 推荐本地端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Backend FastAPI | 8080 | 本项目 API |
| Frontend Next.js | 3001 | 本项目 UI |
| bge-m3 embedding | 8002 | 避开 Attu 的 8000 |
| bge-reranker-v2-m3 | 8003 | 独立 rerank 服务 |
| llama.cpp OpenAI API | 8004 | Qwen3.6 生成服务 |
| Milvus | 19530 | gRPC/REST |
| Milvus WebUI | 9091 | health/webui |
| Attu | 8000 | 当前已占用 |

## 文档入口

- [README.md](README.md)：项目总览、环境判断、快速部署顺序。
- [docs/local-model-audit.md](docs/local-model-audit.md)：本机模型与服务审计结果。
- [docs/technical-solution.md](docs/technical-solution.md)：完整技术方案。
- [docs/development-plan.md](docs/development-plan.md)：按阶段拆解的开发计划。
