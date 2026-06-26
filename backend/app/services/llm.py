from __future__ import annotations

from typing import Any

import httpx


class LLMClientError(RuntimeError):
    pass


class LLMClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 120,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def chat(self, messages: list[dict[str, str]]) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload)
        if response.status_code >= 400:
            raise LLMClientError(
                f"LLM service returned HTTP {response.status_code}: {response.text[:500]}"
            )
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise LLMClientError("LLM service response did not contain choices")
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str):
            raise LLMClientError("LLM service response did not contain message content")
        return content.strip()
