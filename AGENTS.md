# AGENTS.md

本仓库用于建设“飞书知识库本地 RAG”系统：从飞书知识库同步空间、节点、文档与正文 block，解析为可检索 chunk，使用本地 bge-m3、Milvus、bge-reranker-v2-m3 和 Gemma 4 12B IT QAT Q4_0 GGUF 完成本地问答，并返回可追溯来源；Qwen3.6-27B-GGUF Q4_K_M 保留为可选回退/对比模型。

## 当前约束

- 远程仓库：`git@github.com:XueGang-AI/feishu-knowledge-rag.git`
- 不要提交飞书 app secret、tenant access token、用户 cookie、模型下载 token、Milvus 数据目录。

## 运行约定

- 本项目不默认启动 BGE、Reranker、Gemma、Qwen 或 Milvus；默认只连接通用服务地址。
- 通用 Embedding 地址：`http://127.0.0.1:8010`。
- 通用 Reranker 地址：`http://127.0.0.1:8020`。
- 通用 LLM 地址：`http://127.0.0.1:8040/v1`（Gemma 默认）。
- 通用 Qwen 可选/回退/对比地址：`http://127.0.0.1:8030/v1`。
- 通用 Milvus 地址：`http://127.0.0.1:19530`。
- 通用模型服务工程统一放在 `/Users/xuegang/Desktop/My Project/Model/`，模型权重统一放在 `/Users/xuegang/models/`。
- 当前通用模型服务工程：
  - `/Users/xuegang/Desktop/My Project/Model/bge-m3-service`
  - `/Users/xuegang/Desktop/My Project/Model/bge-reranker-service`
  - `/Users/xuegang/Desktop/My Project/Model/qwen-llamacpp-service`
  - `/Users/xuegang/Desktop/My Project/Model/gemma-4-12b-llamacpp-service`
- 本仓库 `scripts/start-reranker.sh`、`scripts/start-qwen-llamacpp.sh`、`scripts/start-gemma-llamacpp.sh` 只是兼容 wrapper，默认调用上述通用服务工程；不要把通用模型服务实现继续扩进 Feishu RAG 业务目录。

## 技术方向

- 后端：Python + FastAPI。
- 同步状态库：SQLite。
- 文档结构：以 JSON block AST 为主，Markdown 为可读中间表示。
- Embedding：调用通用 Embedding 服务。
- 向量库：调用通用 Milvus 服务，collection 维度 1024。
- Rerank：调用通用 Reranker 服务。
- 生成：通过通用 OpenAI-compatible LLM 服务访问 Gemma 4 12B IT QAT Q4_0，默认 `http://127.0.0.1:8040/v1`；Qwen 27B 可作为回退/对比服务运行在 `http://127.0.0.1:8030/v1`。
- 前端：Next.js / React，端口 `3300`。

## 开发原则

- chunk 必须保留来源字段：`chunk_id`、`space_id`、`node_token`、`doc_token`、`doc_type`、`title`、`section_path`、`source_url`、`block_ids`、`content`、`content_hash`、`updated_time`。
- 回答必须返回来源引用，至少可追溯到飞书文档；可用时追溯到 block_id。
- 增量同步以飞书更新时间、block 内容 hash、本地文档 hash 三层判断为准。
- 检索链路固定为：query embedding -> Milvus top 50 -> rerank top 5-8 -> Gemma 默认生成 -> citations。
- 遇到飞书 API 限流、权限不足、文档删除、节点移动时，需要记录同步任务状态，不能静默丢失。

## 推荐本地端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Backend FastAPI | 3301 | 本项目 API |
| Frontend Next.js | 3300 | 本项目 UI |
| 通用 Embedding | 8010 | 本项目只连接，不默认启动 |
| 通用 Reranker | 8020 | 本项目只连接，不默认启动 |
| 通用 LLM OpenAI API | 8040 | Gemma 4 12B，默认生成模型，本项目只连接，不默认启动 |
| 通用 Qwen LLM API | 8030 | Qwen 27B，可选回退/对比模型，本项目只连接，不默认启动 |
| 通用 Milvus | 19530 | 本项目只连接，不默认启动 |

## 文档入口

- [README.md](README.md)：项目总览、环境判断、快速部署顺序。
- [docs/local-model-audit.md](docs/local-model-audit.md)：本机模型与服务审计结果。
- [docs/model-service-split-brief.md](docs/model-service-split-brief.md)：通用模型服务拆分到 `My Project/Model/` 的执行 brief。
- [docs/technical-solution.md](docs/technical-solution.md)：完整技术方案。
- [docs/development-plan.md](docs/development-plan.md)：按阶段拆解的开发计划。
