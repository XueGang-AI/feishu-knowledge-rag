# Model Service Split Brief

## 目标

将通用模型服务工程统一拆到 `/Users/xuegang/Desktop/My Project/Model/` 下，Feishu RAG 项目只保留客户端配置、健康检查和兼容启动 wrapper。

## 目标目录

```text
/Users/xuegang/Desktop/My Project/Model/
  bge-m3-service/
  bge-reranker-service/
  qwen-llamacpp-service/
  gemma-4-12b-llamacpp-service/

/Users/xuegang/models/
  bge-m3
  bge-reranker-v2-m3
  qwen3.6-27b-gguf
  gemma-4-12b-it-qat-q4_0-gguf
```

`/Users/xuegang/models/` 只放模型权重或权重入口；`/Users/xuegang/Desktop/My Project/Model/` 只放服务工程。

## 已完成状态

- `bge-m3-service` 已位于 `/Users/xuegang/Desktop/My Project/Model/bge-m3-service`。
- BGE 权重入口已位于 `/Users/xuegang/models/bge-m3`。
- Feishu RAG 默认仍通过 `http://127.0.0.1:8010` 调用 embedding 服务。
- `bge-reranker-service` 已位于 `/Users/xuegang/Desktop/My Project/Model/bge-reranker-service`，默认引用 `/Users/xuegang/models/bge-reranker-v2-m3`，端口 `8020`，默认 `RERANKER_DEVICE=cpu`。
- `qwen-llamacpp-service` 已位于 `/Users/xuegang/Desktop/My Project/Model/qwen-llamacpp-service`，默认引用 `/Users/xuegang/models/qwen3.6-27b-gguf/Qwen3.6-27B-Q4_K_M.gguf`，端口 `8030`。
- `gemma-4-12b-llamacpp-service` 已位于 `/Users/xuegang/Desktop/My Project/Model/gemma-4-12b-llamacpp-service`，默认引用 `/Users/xuegang/models/gemma-4-12b-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf`，端口 `8040`，是 Feishu RAG 当前默认生成服务。
- Feishu RAG 中 `scripts/start-reranker.sh`、`scripts/start-qwen-llamacpp.sh` 与 `scripts/start-gemma-llamacpp.sh` 已改为兼容 wrapper，默认调用 `Model/` 下的新服务。

## 需要执行

1. 已完成：将 `deploy/reranker` 拆到 `/Users/xuegang/Desktop/My Project/Model/bge-reranker-service`。
2. 已完成：新 service 内保留独立 `pyproject.toml`、`app.py`、`README.md`、`.env.example` 和启动脚本。
3. 已完成：Reranker 权重继续使用 `/Users/xuegang/models/bge-reranker-v2-m3`，对外端口保持 `8020`。
4. 已完成：将 Qwen 的 llama.cpp 启动封装拆到 `/Users/xuegang/Desktop/My Project/Model/qwen-llamacpp-service`。
5. 已完成：Qwen 权重继续使用 `/Users/xuegang/models/qwen3.6-27b-gguf/Qwen3.6-27B-Q4_K_M.gguf`，对外端口保持 `8030`，OpenAI-compatible base URL 保持 `http://127.0.0.1:8030/v1`。
6. 已完成：Feishu RAG 中的 `scripts/start-reranker.sh` 和 `scripts/start-qwen-llamacpp.sh` 改为调用新 service。
7. 已完成：更新 `README.md`、`AGENTS.md`、`docs/local-model-audit.md` 中关于通用模型服务工程位置的说明。
8. 已完成：新增 Gemma 4 12B llama.cpp 服务，默认端口 `8040`，Feishu RAG 使用 `scripts/start-gemma-llamacpp.sh` 作为兼容 wrapper，并将其作为默认生成服务；Qwen 27B 保留在 `8030/v1` 作为可选回退/对比。

## 边界

- 本文记录的是通用模型服务拆分边界；Feishu RAG 当前业务代码已经独立演进，包含多账号隔离、`feishu_chunks_v2`、自动/直接/RAG 问答路由和新版前端。
- 不修改端口规划：Embedding `8010`、Reranker `8020`、Gemma LLM `8040/v1`、Qwen LLM `8030/v1`、Milvus `19530`。
- 不移动或复制大模型权重；只引用 `/Users/xuegang/models/` 下的权重路径。
- 不读取、不输出、不记录 `.env` 中的真实 secret/token/cookie。
- 不删除 `deploy/reranker`，除非新 service 验证通过且用户明确要求清理。

## 验证

```bash
curl -sf http://127.0.0.1:8010/health
curl --max-time 10 -sf \
  --request POST \
  --url http://127.0.0.1:8020/rerank \
  --header "Content-Type: application/json" \
  --data '{"query":"health check","documents":[{"id":"health","text":"health check"}],"top_n":1}'
curl -sf http://127.0.0.1:8040/v1/models
./scripts/check-local-services.sh
# Optional Qwen fallback/comparison:
CHECK_QWEN=true ./scripts/check-local-services.sh
uv run pytest -q
```

若服务已被其他进程占用，先报告监听 PID 和命令，不要直接杀无关进程。

## 交付格式

- 新增/迁移的目录清单。
- 修改过的 Feishu RAG 文件清单。
- 每个服务的启动命令和健康检查结果。
- 未完成项和风险，尤其是依赖缺失、端口占用、旧 wrapper 兼容性。
