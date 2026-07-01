# 按阶段拆解开发方案

## Phase 0：仓库初始化与本地服务基线

目标：把当前空目录变成可开发仓库，并让本地依赖服务可验证。

任务：

- 初始化 git，并关联远程仓库 `git@github.com:XueGang-AI/feishu-knowledge-rag.git`。
- 建立目录结构：`backend/`、`frontend/`、`deploy/`、`docs/`、`data/`。
- 新增 `.env.example`，只放变量名和示例，不放密钥。
- 修复 Milvus 部署路径，或把 compose 复制到 `deploy/milvus/docker-compose.yml`。
- 连接通用 Milvus，验证 `127.0.0.1:19530`。
- 连接通用 Embedding 服务 `8010`，验证 `/v1/embeddings`。
- 下载 bge-reranker-v2-m3。
- 下载默认生成模型 `gemma-4-12b-it-qat-q4_0.gguf`；Qwen 27B 权重保留为可选回退/对比。
- 连接通用 LLM 服务 `8040/v1`，验证 `/chat/completions`。

验收标准：

- `README.md` 中列出的所有本地服务端口可访问。
- bge-m3 返回 1024 维 embedding。
- Milvus 可以创建 collection 并插入测试向量。
- Gemma 可以通过 OpenAI-compatible API 返回测试回答；Qwen 可按需作为可选回退/对比验证。

## Phase 1：后端基础工程

目标：建立 FastAPI 后端骨架、配置系统、状态库和健康检查。

任务：

- 创建 FastAPI 项目结构。
- 使用 Pydantic Settings 管理配置。
- 创建 SQLite schema 和 migration 机制。
- 实现 `/health`，检查 SQLite、Milvus、embedding、reranker、LLM 的连通性。
- 实现统一日志、请求 ID、错误响应格式。
- 增加基础测试。

验收标准：

- `GET /health` 返回各依赖服务状态。
- SQLite 表可自动初始化。
- 配置缺失时错误清晰，不泄露 secret。

## Phase 2：飞书 API Client 与同步任务

目标：能够读取飞书知识空间、节点和文档元信息，记录同步状态。

任务：

- 实现 tenant access token 获取与刷新。
- 实现知识空间列表、节点信息、节点遍历。
- 实现文档元信息读取。
- 建立 `sync_jobs`、`spaces`、`nodes`、`documents` 表写入逻辑。
- 实现 `POST /api/sync/jobs`、`GET /api/sync/jobs/{job_id}`。
- 加入限流、重试、失败记录。

验收标准：

- 可以按 `space_id` 或 `node_token` 创建同步任务。
- 同步任务能记录进度、成功数、失败数。
- 权限不足和限流能被记录并展示。

## Phase 3：Docx Block 解析与结构化

目标：读取飞书云文档 block，保留标题层级和 block_id。

任务：

- 实现 docx block 拉取。
- 建立 block AST。
- 支持标题、正文、列表、表格、代码块。
- 维护 heading stack，生成 `section_path`。
- 将 block 快照写入 `blocks` 表。
- 生成 Markdown 调试输出。

验收标准：

- 每个 block 都有 `block_id` 和类型。
- 标题路径正确。
- 文档内容可还原为可读 Markdown。
- 对不支持的 block 类型保留占位信息，不导致同步失败。

## Phase 4：Chunker 与增量 hash

目标：把结构化文档切为适合检索的 chunk，并支持增量判断。

任务：

- 实现按标题层级切块。
- 实现语义边界合并和 overlap。
- 为每个 chunk 生成稳定 `chunk_id`。
- 计算 `content_hash`。
- 写入 `chunks` 表。
- 实现文档未变更跳过切块，chunk 未变更跳过 embedding。

验收标准：

- chunk 包含 `title`、`section_path`、`block_ids`、`content`。
- 不跨一级标题切块。
- 重复同步同一文档不会产生重复 chunk。
- 修改单个文档只影响对应文档 chunk。

## Phase 5：Embedding 与 Milvus 索引

目标：将 chunk 写入 Milvus，并能通过向量召回。

任务：

- 实现 bge-m3 embedding client。
- 创建 Milvus collection `feishu_chunks_v2`，并保留 `feishu_chunks_v1` 作为默认账号旧数据 fallback。
- 建立 1024 维向量 schema 和 metadata 字段。
- 实现 chunk upsert。
- 实现过期 chunk 删除或软删除。
- 实现 `POST /api/search` 初版：query embedding -> Milvus top 50。

验收标准：

- Milvus 中 chunk metadata 完整。
- 搜索返回 `chunk_id`、`content`、`source_url`、`block_ids`。
- 重复索引是幂等的。

## Phase 6：Rerank 与检索质量

目标：在 Milvus 召回后使用 bge-reranker-v2-m3 精排。

任务：

- 部署 reranker 服务或后端内嵌 reranker。
- 实现 rerank client。
- `POST /api/search` 返回 raw score 和 rerank score。
- 支持 top_k、top_n、account_id、space_id、doc_token 过滤。
- 增加简单评测集：问题、期望文档、期望标题路径。

验收标准：

- 默认 Milvus top 50，rerank top 8。
- 返回结果按 rerank score 排序。
- 相同 query 多次请求结果稳定。

## Phase 7：Gemma 生成与来源引用

目标：实现完整问答，答案必须带来源引用。

任务：

- 实现 llama.cpp OpenAI-compatible client。
- 设计 RAG prompt。
- 将 top 5-8 chunk 编号为 `[S1]`、`[S2]`。
- 实现 citation builder。
- 实现 `POST /api/chat`。
- 支持 `mode=auto|direct|rag`：普通问题 direct，知识库/文档范围问题 RAG。
- 支持流式输出时最后返回完整 sources。

验收标准：

- 答案中的关键结论带 `[Sx]`。
- `sources` 可追溯到 `source_url` 和 `block_ids`。
- 未检索到可靠来源时，回答“当前知识库未找到相关内容”。
- 不允许生成不存在的飞书链接或 block_id。

## Phase 8：同步管理与重新索引

目标：支持后续增量同步、重新索引和同步状态查看。

任务：

- 实现定向 reindex：按空间、节点、文档。
- 实现删除同步：飞书删除后本地失效。
- 实现任务取消。
- 实现 `GET /api/sync/status`。
- 实现 `POST /api/reindex`。
- 实现 weekly scan 调度和手动触发入口。
- 增加 index event 日志。

验收标准：

- 可以查看最近同步时间、文档数、chunk 数、失败数。
- 可以对单个文档重新索引；document scope 的 `scope_id` 为 `space_id:node_token`。
- 删除的文档不会再被检索到。

## Phase 9：前端界面

目标：提供聊天、来源查看和同步管理 UI。

任务：

- 创建 Next.js / React 项目。
- 实现 Chat 页面。
- 实现来源侧栏：标题、section_path、content_preview、飞书链接、block_ids。
- 实现 Sync 页面：创建任务、查看进度、失败详情。
- 实现 Documents 页面：文档索引状态。
- 实现 Settings 页面：通用服务健康检查。
- 实现真实搜索、文档详情、健康度和系统提醒视图。

验收标准：

- 打开 `http://127.0.0.1:3300` 即进入可用聊天界面。
- 每条回答可展开来源。
- 同步任务状态实时刷新。

## Phase 10：质量、运维与发布

目标：让系统可长期本地使用和维护。

任务：

- 增加端到端 smoke test。
- 增加检索评测脚本。
- 增加备份与恢复说明。
- 增加日志轮转。
- 增加模型服务启动检查脚本。
- 整理部署文档。

验收标准：

- 一条命令可检查所有本地依赖服务状态。
- 有最小评测集衡量召回和答案引用质量。
- 本地数据目录和密钥目录明确，不会误提交。

## 首个可用版本范围

MVP 只包含：

- 飞书 docx 文档同步。
- 标题、正文、列表、表格、代码块解析。
- chunk + embedding + Milvus。
- search + rerank + chat。
- 答案来源引用。
- 手动同步和手动 reindex。

MVP 暂不包含：

- 飞书表格、多维表格、图片 OCR、附件解析。
- 多用户权限继承。
- 分布式任务队列。
- 完整用户权限继承。
