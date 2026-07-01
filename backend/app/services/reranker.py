from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx


class RerankerClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class RerankResult:
    id: str
    score: float
    rank: int


class RerankerClient:
    def __init__(self, base_url: str, model: str, timeout_seconds: float = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def rerank(
        self,
        query: str,
        documents: list[dict[str, str]],
        top_n: int,
    ) -> list[RerankResult]:
        if not documents:
            return []
        payload: dict[str, Any] = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/rerank", json=payload)
            if response.status_code >= 500:
                await asyncio.sleep(0.5)
                response = await client.post(f"{self.base_url}/rerank", json=payload)
        if response.status_code >= 400:
            raise RerankerClientError(f"reranker service returned HTTP {response.status_code}")
        data = response.json()
        results = data.get("results")
        if not isinstance(results, list):
            raise RerankerClientError("reranker service response did not contain results list")
        return [
            RerankResult(id=str(item["id"]), score=float(item["score"]), rank=int(item["rank"]))
            for item in results
        ]
