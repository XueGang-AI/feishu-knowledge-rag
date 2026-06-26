from __future__ import annotations

from typing import Any

import httpx


class EmbeddingClientError(RuntimeError):
    pass


class EmbeddingClient:
    def __init__(self, base_url: str, model: str, timeout_seconds: float = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload: dict[str, Any] = {"model": self.model, "input": texts}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/v1/embeddings", json=payload)
        if response.status_code >= 400:
            raise EmbeddingClientError(f"embedding service returned HTTP {response.status_code}")
        data = response.json()
        embeddings = data.get("data")
        if not isinstance(embeddings, list):
            raise EmbeddingClientError("embedding service response did not contain data list")
        return [
            item["embedding"] for item in sorted(embeddings, key=lambda item: item.get("index", 0))
        ]
