import asyncio
from typing import Any

import httpx
from fastapi import APIRouter

from backend.app.core.config import get_settings
from backend.app.db.sqlite import initialize_database, ping

router = APIRouter(tags=["health"])

HEALTHCHECK_TIMEOUT_CAP_SECONDS = 3.0


def _health_timeout(configured_timeout: float) -> float:
    return min(configured_timeout, HEALTHCHECK_TIMEOUT_CAP_SECONDS)


async def _check_http_get(name: str, url: str, timeout_seconds: float) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(url)
        return {
            "name": name,
            "ok": 200 <= response.status_code < 400,
            "status_code": response.status_code,
            "url": url,
        }
    except Exception as exc:
        return {"name": name, "ok": False, "url": url, "error": str(exc)}


async def _check_http_post(
    name: str,
    url: str,
    timeout_seconds: float,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, json=payload)
        return {
            "name": name,
            "ok": 200 <= response.status_code < 400,
            "status_code": response.status_code,
            "url": url,
        }
    except Exception as exc:
        return {"name": name, "ok": False, "url": url, "error": str(exc)}


@router.get("/health")
async def health() -> dict[str, Any]:
    settings = get_settings()
    checks: dict[str, Any] = {}

    try:
        initialize_database(settings.sqlite_path)
        ping(settings.sqlite_path)
        checks["sqlite"] = {
            "name": "sqlite",
            "ok": True,
            "path": str(settings.sqlite_path),
        }
    except Exception as exc:
        checks["sqlite"] = {
            "name": "sqlite",
            "ok": False,
            "path": str(settings.sqlite_path),
            "error": str(exc),
        }

    checks["feishu"] = {
        "name": "feishu",
        "ok": settings.feishu_credentials_configured,
        "configured": settings.feishu_credentials_configured,
        "accounts": settings.public_feishu_accounts,
    }

    embedding, reranker, llm, milvus = await asyncio.gather(
        _check_http_get(
            "embedding",
            f"{settings.embedding_base_url}/health",
            _health_timeout(settings.embedding_timeout_seconds),
        ),
        _check_http_post(
            "reranker",
            f"{settings.reranker_base_url}/rerank",
            _health_timeout(settings.reranker_timeout_seconds),
            {
                "model": settings.reranker_model,
                "query": "health check",
                "documents": [{"id": "health", "text": "health check"}],
                "top_n": 1,
            },
        ),
        _check_http_get(
            "llm",
            f"{settings.llm_base_url}/models",
            _health_timeout(settings.llm_timeout_seconds),
        ),
        _check_http_post(
            "milvus",
            f"{settings.milvus_uri}/v2/vectordb/collections/list",
            _health_timeout(settings.milvus_timeout_seconds),
            {"dbName": settings.milvus_db},
        ),
    )
    checks["embedding"] = embedding
    checks["reranker"] = reranker
    checks["llm"] = llm
    checks["milvus"] = milvus

    required = ["sqlite"]
    optional = ["feishu", "embedding", "reranker", "llm", "milvus"]
    return {
        "status": "ok" if all(checks[name]["ok"] for name in required) else "degraded",
        "required": required,
        "optional": optional,
        "checks": checks,
    }
