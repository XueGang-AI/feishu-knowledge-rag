# 完整技术方案

## 目标

从飞书知识库同步内容，包括知识库空间、节点、文档、标题层级和正文 block；将飞书文档解析为适合检索的本地文本 chunk；用 bge-m3 生成 embedding，写入 Milvus；查询时先召回再用 bge-reranker-v2-m3 精排；最后默认用本地 Gemma 4 12B IT QAT Q4_0 GGUF 生成答案，并返回可追溯到飞书文档或 block 的来源引用。Qwen3.6-27B-GGUF Q4_K_M 保留为可选回退/对比模型。

## 总体架构

```text
              +------------------+
              |   Next.js UI     |
              +---------+--------+
                        |
                        v
              +------------------+
              |  FastAPI Backend |
              +----+--------+----+
                   |        |
       sync/index  |        | query/chat
                   |        |
                   v        v
     +----------------+   +----------------+
     | Feishu Client  |   | Retrieval Flow |
     +-------+--------+   +---+-------+----+
             |                |       |
             v                v       v
    +-----------------+  bge-m3    Milvus
    | Parser/Chunker  |    |        |
    +--------+--------+    v        v
             |       bge-reranker   top chunks
             v             |
    +-----------------+    v
    | SQLite State DB |  llama.cpp / Gemma
    +-----------------+    |
                           v
                     answer + sources
```

## 模块划分

| 模块 | 职责 |
|------|------|
| Feishu Client | 鉴权、列出知识空间、遍历节点、读取文档元信息和 block |
| Sync Worker | 创建同步任务、增量判断、失败重试、状态记录 |
| Document Parser | 将飞书 block 转换为结构化 AST 和 Markdown |
| Chunker | 按标题路径、语义边界、block 边界切分 chunk |
| Embedding Client | 调用本地 bge-m3 服务生成 1024 维向量 |
| Milvus Indexer | 创建 collection、upsert chunk、删除过期 chunk |
| SQLite Store | 保存空间、节点、文档、block、chunk、任务状态和 hash |
| Retriever | query embedding、Milvus top 50 召回、metadata 过滤 |
| Reranker | 调用 bge-reranker-v2-m3，返回 top 5-8 |
| Answer Generator | 构造上下文，调用 llama.cpp OpenAI API |
| Citation Builder | 生成答案引用，映射到文档 URL 和 block_id |
| Frontend | 聊天、来源查看、同步管理、状态查看 |

## 飞书同步设计

### 鉴权

使用飞书开放平台自建应用：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- tenant access token 缓存到本地内存和 SQLite，不写入日志。
- token 过期前刷新。

### 同步范围

支持三种同步粒度：

| 粒度 | 说明 |
|------|------|
| 全量同步 | 遍历所有已授权知识空间和节点 |
| 空间同步 | 只同步指定 `space_id` |
| 节点同步 | 从指定 `node_token` 开始同步子树 |

### 飞书对象映射

| 飞书对象 | 本地表 | 关键字段 |
|----------|--------|----------|
| 知识空间 | `spaces` | `account_id`, `space_id`, `name`, `description` |
| 知识库节点 | `nodes` | `account_id`, `space_id`, `node_token`, `parent_node_token`, `obj_token`, `obj_type`, `title` |
| 云文档 | `documents` | `account_id`, `doc_token`, `doc_type`, `title`, `source_url`, `updated_time` |
| 文档 block | `blocks` | `account_id`, `block_id`, `doc_token`, `parent_block_id`, `block_type`, `hash` |
| 检索 chunk | `chunks` | `account_id`, `chunk_id`, `doc_token`, `section_path`, `block_ids`, `content_hash`, `indexed_at` |

### 增量同步

增量同步采用三层判断：

1. 节点层：飞书节点 `updated_time` 未变化则跳过文档拉取。
2. 文档层：文档 block 列表 hash 未变化则跳过切块。
3. chunk 层：chunk `content_hash` 未变化则跳过 embedding 和 Milvus upsert。

删除与移动：

- 飞书节点不存在：标记 `nodes.deleted_at`，删除或失效相关 chunk。
- 文档移动：更新 `space_id`、`node_token`、`section_path` 和来源 URL。
- block 删除：重新生成该文档 chunk，删除旧 chunk。

### 限流与重试

- 对飞书 API 使用全局速率限制器。
- 429、5xx 使用指数退避。
- 403 记录权限错误，不无限重试。
- 单文档失败不能中断整个空间同步。

## 文档解析与切块

### 中间结构

每个文档解析为 block AST：

```json
{
  "doc_token": "docxxx",
  "title": "知识库接入说明",
  "blocks": [
    {
      "block_id": "blk_xxx",
      "parent_block_id": null,
      "type": "heading",
      "heading_level": 1,
      "text": "接入流程",
      "children": []
    }
  ]
}
```

同时生成 Markdown 作为调试和人工查看格式。检索以 AST 切块为准，Markdown 只作为可读表示。

### 标题路径

解析 heading block 时维护标题栈：

```text
一级标题 > 二级标题 > 三级标题
```

每个 chunk 保存 `section_path`。如果正文在文档开头且没有标题，则使用文档标题作为 section path。

### 切块策略

切块目标：

- 中文文本目标长度：约 500-900 字。
- 最大长度：约 1200-1500 字，避免超长上下文。
- overlap：约 80-120 字，仅在连续正文中使用。
- 表格、代码块、列表优先保持完整。
- 一个 chunk 可以包含多个 block，但必须保存 `block_ids` 数组。
- 不跨一级标题切 chunk；二级以下标题可在小节太短时合并。

chunk 文本模板：

```text
文档：{title}
章节：{section_path}

{content}
```

`content_hash` 对规范化后的 chunk content、section_path、block_ids 计算 SHA-256。

## Milvus 设计

### Collection

collection 名称：

```text
feishu_chunks_v2
```

旧 collection `feishu_chunks_v1` 仅作为默认账号的 fallback collection。

向量维度：

```text
1024
```

metric：

```text
COSINE
```

### Schema

| 字段 | 类型 | 说明 |
|------|------|------|
| `chunk_id` | VarChar primary key | 稳定 chunk ID |
| `account_id` | VarChar | 飞书账号/租户标识 |
| `space_id` | VarChar | 知识空间 ID |
| `node_token` | VarChar | 知识库节点 token |
| `doc_token` | VarChar | 文档 token |
| `doc_type` | VarChar | docx、wiki、sheet 等 |
| `title` | VarChar | 文档标题 |
| `section_path` | VarChar | 标题路径 |
| `source_url` | VarChar | 飞书文档链接 |
| `block_ids` | JSON 或 VarChar | block_id 数组 |
| `content` | VarChar | chunk 正文 |
| `content_hash` | VarChar | 内容 hash |
| `updated_time` | Int64 | 飞书更新时间 |
| `embedding` | FloatVector(1024) | bge-m3 dense vector |

### 索引参数

本地开发建议：

```json
{
  "index_type": "HNSW",
  "metric_type": "COSINE",
  "params": {
    "M": 16,
    "efConstruction": 200
  }
}
```

搜索参数：

```json
{
  "metric_type": "COSINE",
  "params": {
    "ef": 64
  }
}
```

如果 HNSW 在当前 Milvus 版本或资源下不稳定，则降级到 `AUTOINDEX`。

## SQLite 状态库

SQLite 文件建议：

```text
data/state/feishu_rag.sqlite3
```

核心表：

| 表 | 说明 |
|----|------|
| `sync_jobs` | 同步任务、状态、进度、错误 |
| `spaces` | 知识空间 |
| `nodes` | 知识库节点树 |
| `documents` | 文档元信息 |
| `blocks` | block 快照和 hash |
| `chunks` | chunk 元信息、hash、索引状态 |
| `index_events` | upsert/delete/reindex 事件 |
| `settings` | 本地配置快照 |

任务状态：

```text
pending -> running -> succeeded
pending -> running -> failed
pending -> running -> cancelled
```

## 检索与问答

### Search Flow

1. 用户输入 query。
2. 调用 bge-m3 生成 query embedding。
3. Milvus 召回 top 50。
4. 按 `account_id`、`space_id`、`doc_token` 过滤 chunk。
5. bge-reranker-v2-m3 对 query 和 chunk content 打分。
6. 取 top 5-8 作为 LLM context。

如果 Reranker 推理接口返回错误，后端降级使用 Milvus 原始召回 topN，继续返回结果并将 `rerank_score` 置为 `null`；`/health` 使用真实 `/rerank` 探针展示 reranker 推理可用性。

### Prompt Context

上下文按引用编号组织：

```text
[S1]
title: 知识库接入说明
section: 接入流程 > 权限配置
url: https://...
block_ids: blk_xxx, blk_yyy
content:
...
```

系统要求：

- 只能基于给定来源回答。
- 不确定时说明未在当前知识库中找到。
- 每个关键结论后标注来源，如 `[S1]`。
- 不编造飞书链接或 block_id。

### Response Schema

`POST /api/chat` 请求支持：

```json
{
  "query": "问题",
  "mode": "auto",
  "account_id": "default",
  "space_id": null,
  "doc_token": null,
  "top_k": 50,
  "top_n": 8
}
```

`mode=auto` 会把普通问题直接交给 Gemma；涉及飞书知识库、文档范围或项目资料时走 RAG。`mode=direct` 强制不检索，`mode=rag` 强制检索。

`POST /api/chat` 返回：

```json
{
  "answer": "申请权限需要先... [S1]",
  "sources": [
    {
      "source_id": "S1",
      "chunk_id": "chunk_xxx",
      "account_id": "default",
      "space_id": "spc_xxx",
      "node_token": "nod_xxx",
      "doc_token": "doc_xxx",
      "title": "知识库接入说明",
      "section_path": "接入流程 > 权限配置",
      "source_url": "https://...",
      "block_ids": ["blk_xxx"],
      "score": 0.87,
      "rerank_score": 0.91,
      "updated_time": 1782499200,
      "content_preview": "..."
    }
  ],
  "mode": "rag",
  "retrieval_used": true
}
```

## 后端 API

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/health` | 服务健康检查 |
| `POST` | `/api/sync/jobs` | 创建同步任务 |
| `GET` | `/api/sync/jobs` | 同步任务列表 |
| `GET` | `/api/sync/jobs/{job_id}` | 同步任务详情 |
| `POST` | `/api/sync/jobs/{job_id}/run` | 启动已创建任务 |
| `POST` | `/api/sync/jobs/{job_id}/cancel` | 取消任务 |
| `GET` | `/api/sync/status` | 同步状态总览 |
| `POST` | `/api/reindex` | 重建索引 |
| `POST` | `/api/sync/weekly-scan/run` | 手动触发 weekly scan |
| `POST` | `/api/search` | 检索 chunks |
| `POST` | `/api/chat` | 问答 |
| `GET` | `/api/sources/{chunk_id}` | 查看来源详情 |

## 前端设计

页面：

| 页面 | 功能 |
|------|------|
| 首页总览 | 真实健康状态、索引统计、快捷提问、提醒入口 |
| 智能问答 | 自动/强制知识库问答、来源引用、直接回答状态 |
| 知识库管理 | 多账号集合状态、最近来源、文档入口 |
| 导入文档 | 创建同步任务、选择 all/account/space/node/document 范围、weekly scan |
| 长期记忆 | 当前浏览器本地记忆展示 |
| 检索测试 | 真实 `/api/search` 检索和来源打开 |
| 本地设置 | API base、服务健康、问答偏好、账号范围 |
| 健康度/系统提醒 | 根据服务、chunks、同步任务和账号错误推导 |

交互原则：

- 聊天页第一屏就是可用的问答界面。
- 来源引用可点击，打开飞书链接。
- 同步任务显示 running/succeeded/failed/cancelled。
- 失败任务展示失败节点、文档和错误原因。
- 文档详情里的“用此文档提问/生成摘要”用 `doc_token` 做检索过滤；“重新索引”用 `space_id:node_token` 创建 document scope 任务。

## 部署拓扑

```text
127.0.0.1:3300  frontend
127.0.0.1:3301  backend
127.0.0.1:8010  通用 Embedding
127.0.0.1:8020  通用 Reranker
127.0.0.1:8040  通用 LLM OpenAI API（Gemma 默认）
127.0.0.1:8030  通用 Qwen OpenAI API（可选/回退/对比）
127.0.0.1:19530 通用 Milvus
```

## 配置示例

```env
FEISHU_APP_ID=
FEISHU_APP_SECRET=

SQLITE_PATH=data/state/feishu_rag.sqlite3

EMBEDDING_BASE_URL=http://127.0.0.1:8010
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024

MILVUS_URI=http://127.0.0.1:19530
MILVUS_DB=default
MILVUS_COLLECTION=feishu_chunks_v2
MILVUS_LEGACY_COLLECTION=feishu_chunks_v1

RERANKER_BASE_URL=http://127.0.0.1:8020
RERANKER_MODEL=BAAI/bge-reranker-v2-m3

LLM_BASE_URL=http://127.0.0.1:8040/v1
LLM_MODEL=gemma-4-12b-it-qat-q4_0
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=2048

# Optional Qwen 27B fallback/comparison:
# LLM_BASE_URL=http://127.0.0.1:8030/v1
# LLM_MODEL=Qwen3.6-27B-GGUF:Q4_K_M
```

## 风险与处理

| 风险 | 处理 |
|------|------|
| 飞书 API 权限不足 | 同步任务记录 403 和对应节点，前端提示授权范围 |
| 飞书 API 限流 | 全局 limiter + 指数退避 |
| 文档 block 类型复杂 | 先覆盖标题、正文、列表、表格、代码块，图片/附件后续扩展 |
| Milvus 容器路径不一致 | 将 compose 固化到本项目或修正现有脚本 |
| 通用模型服务不可用 | 健康检查标记为 unavailable，前后端不自动拉起外部模型服务 |
| 生成模型上下文过长 | rerank 后 top 5-8，按 token budget 截断 |
| 引用不准确 | 所有 prompt context 强制带 `source_id`、`chunk_id`、`block_ids` |
| 重复 chunk | `content_hash` + `chunk_id` 稳定生成，upsert 幂等 |
