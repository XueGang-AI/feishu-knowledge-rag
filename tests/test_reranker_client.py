import pytest

import backend.app.services.reranker as reranker_module
from backend.app.services.reranker import RerankerClient


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class FakeAsyncClient:
    calls = 0

    def __init__(self, *args, **kwargs) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def post(self, *args, **kwargs) -> FakeResponse:
        self.__class__.calls += 1
        if self.__class__.calls == 1:
            return FakeResponse(500)
        return FakeResponse(
            200,
            {"results": [{"id": "chunk_1", "score": 0.9, "rank": 1}]},
        )


@pytest.mark.asyncio
async def test_reranker_retries_transient_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAsyncClient.calls = 0

    async def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(reranker_module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(reranker_module.asyncio, "sleep", no_sleep)

    results = await RerankerClient("http://127.0.0.1:8020", "reranker").rerank(
        query="Milvus 是什么",
        documents=[{"id": "chunk_1", "text": "Milvus 是向量数据库"}],
        top_n=1,
    )

    assert FakeAsyncClient.calls == 2
    assert results[0].id == "chunk_1"
    assert results[0].score == 0.9
