from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

DEFAULT_MODEL_PATH = "/Users/xuegang/models/bge-reranker-v2-m3"


class RerankDocument(BaseModel):
    id: str
    text: str


class RerankRequest(BaseModel):
    query: str = Field(min_length=1)
    documents: list[RerankDocument]
    top_n: int = Field(default=8, ge=1, le=100)
    model: str | None = None


class RerankResult(BaseModel):
    id: str
    score: float
    rank: int


class RerankResponse(BaseModel):
    model: str
    results: list[RerankResult]


def model_id() -> str:
    return os.getenv("RERANKER_MODEL_PATH") or os.getenv(
        "RERANKER_MODEL", DEFAULT_MODEL_PATH
    )


def reranker_device() -> str | None:
    value = os.getenv("RERANKER_DEVICE", "cpu").strip()
    if value.lower() in {"", "auto", "none"}:
        return None
    return value


@lru_cache
def load_reranker() -> Any:
    from FlagEmbedding import FlagReranker

    use_fp16 = os.getenv("RERANKER_USE_FP16", "false").lower() == "true"
    device = reranker_device()
    kwargs = {"devices": device} if device else {}
    return FlagReranker(model_id(), use_fp16=use_fp16, **kwargs)


app = FastAPI(title="BGE Reranker Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "model": model_id(), "device": reranker_device() or "auto"}


@app.post("/rerank", response_model=RerankResponse)
def rerank(request: RerankRequest) -> RerankResponse:
    reranker = load_reranker()
    pairs = [[request.query, document.text] for document in request.documents]
    raw_scores = reranker.compute_score(pairs)
    if not isinstance(raw_scores, list):
        raw_scores = [raw_scores]
    ranked = sorted(
        zip(request.documents, raw_scores, strict=True),
        key=lambda item: float(item[1]),
        reverse=True,
    )[: request.top_n]
    return RerankResponse(
        model=model_id(),
        results=[
            RerankResult(id=document.id, score=float(score), rank=index)
            for index, (document, score) in enumerate(ranked, start=1)
        ],
    )
