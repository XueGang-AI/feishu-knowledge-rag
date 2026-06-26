from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


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
    return os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")


@lru_cache
def load_reranker() -> Any:
    from FlagEmbedding import FlagReranker

    use_fp16 = os.getenv("RERANKER_USE_FP16", "false").lower() == "true"
    return FlagReranker(model_id(), use_fp16=use_fp16)


app = FastAPI(title="BGE Reranker Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "model": model_id()}


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
