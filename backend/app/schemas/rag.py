from typing import Literal

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    source_id: str
    chunk_id: str
    account_id: str
    space_id: str
    node_token: str
    doc_token: str
    tenant_name: str | None = None
    title: str
    section_path: str
    source_url: str | None
    block_ids: list[str]
    score: float | None = None
    rerank_score: float | None = None
    updated_time: int | None = None
    content_preview: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=100)
    top_n: int | None = Field(default=None, ge=1, le=20)
    account_id: str | None = None
    space_id: str | None = None
    doc_token: str | None = None


class SearchHit(BaseModel):
    chunk_id: str
    account_id: str
    space_id: str
    node_token: str
    doc_token: str
    tenant_name: str | None = None
    title: str
    section_path: str
    source_url: str | None
    block_ids: list[str]
    content: str
    score: float | None = None
    rerank_score: float | None = None
    updated_time: int | None = None


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: Literal["auto", "direct", "rag"] = "auto"
    top_k: int | None = Field(default=None, ge=1, le=100)
    top_n: int | None = Field(default=None, ge=1, le=20)
    account_id: str | None = None
    space_id: str | None = None
    doc_token: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceRef]
    mode: Literal["direct", "rag"]
    retrieval_used: bool
