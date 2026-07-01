import pytest

import backend.app.services.rag as rag_module
from backend.app.core.config import Settings
from backend.app.schemas.rag import SearchHit, SearchResponse
from backend.app.services.rag import RAGService
from backend.app.services.reranker import RerankerClientError


def _settings() -> Settings:
    return Settings(
        LLM_BASE_URL="http://127.0.0.1:8040/v1",
        LLM_MODEL="gemma-4-12b-it-qat-q4_0",
        FEISHU_ACCOUNTS_JSON="",
        FEISHU_APP_ID="",
        FEISHU_APP_SECRET="",
        WEEKLY_SCAN_ENABLED=False,
        _env_file=None,
    )


class ForbiddenClient:
    def __init__(self, *args, **kwargs) -> None:
        raise AssertionError("direct chat must not instantiate retrieval clients")


class FakeLLMClient:
    calls: list[list[dict[str, str]]] = []

    def __init__(self, *args, **kwargs) -> None:
        return None

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return "直接回答"


class FakeEmbeddingClient:
    def __init__(self, *args, **kwargs) -> None:
        return None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


class FakeVectorStore:
    def __init__(self, *args, **kwargs) -> None:
        return None

    def search(self, *args, **kwargs) -> list[dict]:
        return [
            {
                "chunk_id": "chunk_1",
                "account_id": "default",
                "space_id": "space_1",
                "node_token": "node_1",
                "doc_token": "doc_1",
                "title": "Milvus",
                "section_path": "Milvus",
                "source_url": "https://feishu.cn/wiki/node_1",
                "block_ids": ["block_1"],
                "content": "Milvus 是向量数据库",
                "score": 0.7,
                "updated_time": 1,
            }
        ]


class FailingRerankerClient:
    def __init__(self, *args, **kwargs) -> None:
        return None

    async def rerank(self, *args, **kwargs):
        raise RerankerClientError("reranker failed")


@pytest.mark.asyncio
async def test_direct_mode_does_not_use_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeLLMClient.calls = []
    monkeypatch.setattr(rag_module, "EmbeddingClient", ForbiddenClient)
    monkeypatch.setattr(rag_module, "RerankerClient", ForbiddenClient)
    monkeypatch.setattr(rag_module, "MilvusVectorStore", ForbiddenClient)
    monkeypatch.setattr(rag_module, "LLMClient", FakeLLMClient)

    response = await RAGService(_settings()).chat("帮我写一句欢迎语", mode="direct")

    assert response.mode == "direct"
    assert response.retrieval_used is False
    assert response.sources == []
    assert response.answer == "直接回答"
    assert FakeLLMClient.calls


@pytest.mark.asyncio
async def test_auto_routes_model_identity_to_direct_without_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rag_module, "EmbeddingClient", ForbiddenClient)
    monkeypatch.setattr(rag_module, "RerankerClient", ForbiddenClient)
    monkeypatch.setattr(rag_module, "MilvusVectorStore", ForbiddenClient)

    response = await RAGService(_settings()).chat("你好，你是什么模型")

    assert response.mode == "direct"
    assert response.retrieval_used is False
    assert response.sources == []
    assert "Gemma" in response.answer
    assert "8040" in response.answer


@pytest.mark.asyncio
async def test_rag_mode_uses_search_and_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    search_calls: list[str] = []
    FakeLLMClient.calls = []

    async def fake_search(self: RAGService, query: str, **kwargs) -> SearchResponse:
        search_calls.append(query)
        return SearchResponse(
            query=query,
            hits=[
                SearchHit(
                    chunk_id="chunk_1",
                    account_id="default",
                    space_id="space_1",
                    node_token="node_1",
                    doc_token="doc_1",
                    tenant_name="当前企业",
                    title="文搜图",
                    section_path="文搜图",
                    source_url="https://feishu.cn/wiki/N5iOwEEediOFCkkgclvcLyI7nsJ",
                    block_ids=["block_1"],
                    content="文搜图知识库内容",
                    score=0.8,
                    rerank_score=0.9,
                    updated_time=1,
                )
            ],
        )

    monkeypatch.setattr(RAGService, "search", fake_search)
    monkeypatch.setattr(rag_module, "LLMClient", FakeLLMClient)

    response = await RAGService(_settings()).chat("文搜图是什么", mode="rag")

    assert search_calls == ["文搜图是什么"]
    assert response.mode == "rag"
    assert response.retrieval_used is True
    assert response.sources[0].source_id == "S1"
    assert response.sources[0].space_id == "space_1"
    assert response.sources[0].node_token == "node_1"
    assert response.sources[0].doc_token == "doc_1"
    assert FakeLLMClient.calls


@pytest.mark.asyncio
async def test_auto_routes_weekly_report_to_rag(monkeypatch: pytest.MonkeyPatch) -> None:
    search_calls: list[str] = []

    async def fake_search(self: RAGService, query: str, **kwargs) -> SearchResponse:
        search_calls.append(query)
        return SearchResponse(query=query, hits=[])

    monkeypatch.setattr(RAGService, "search", fake_search)

    response = await RAGService(_settings()).chat("6.28 周报讲了什么")

    assert search_calls == ["6.28 周报讲了什么"]
    assert response.mode == "rag"
    assert response.retrieval_used is True
    assert response.sources == []


@pytest.mark.asyncio
async def test_search_falls_back_to_vector_hits_when_reranker_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rag_module, "EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(rag_module, "MilvusVectorStore", FakeVectorStore)
    monkeypatch.setattr(rag_module, "RerankerClient", FailingRerankerClient)

    response = await RAGService(_settings()).search("Milvus 是什么", top_n=1)

    assert len(response.hits) == 1
    assert response.hits[0].chunk_id == "chunk_1"
    assert response.hits[0].score == 0.7
    assert response.hits[0].rerank_score is None
