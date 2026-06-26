from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="local", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8080, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_allow_origins: list[str] = Field(
        default=["http://127.0.0.1:3001", "http://localhost:3001"],
        alias="CORS_ALLOW_ORIGINS",
    )

    sqlite_path: Path = Field(
        default=Path("data/state/feishu_rag.sqlite3"),
        alias="SQLITE_PATH",
    )

    feishu_base_url: str = Field(default="https://open.feishu.cn", alias="FEISHU_BASE_URL")
    feishu_app_id: str | None = Field(default=None, alias="FEISHU_APP_ID")
    feishu_app_secret: str | None = Field(default=None, alias="FEISHU_APP_SECRET")
    feishu_request_timeout_seconds: float = Field(
        default=30, alias="FEISHU_REQUEST_TIMEOUT_SECONDS"
    )
    feishu_page_size: int = Field(default=50, alias="FEISHU_PAGE_SIZE")

    embedding_base_url: str = Field(default="http://127.0.0.1:8002", alias="EMBEDDING_BASE_URL")
    embedding_model: str = Field(default="BAAI/bge-m3", alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(default=1024, alias="EMBEDDING_DIM")
    embedding_timeout_seconds: float = Field(default=60, alias="EMBEDDING_TIMEOUT_SECONDS")

    milvus_uri: str = Field(default="http://127.0.0.1:19530", alias="MILVUS_URI")
    milvus_db: str = Field(default="default", alias="MILVUS_DB")
    milvus_collection: str = Field(default="feishu_chunks_v1", alias="MILVUS_COLLECTION")
    milvus_timeout_seconds: float = Field(default=5, alias="MILVUS_TIMEOUT_SECONDS")

    reranker_base_url: str = Field(default="http://127.0.0.1:8003", alias="RERANKER_BASE_URL")
    reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3", alias="RERANKER_MODEL")
    reranker_timeout_seconds: float = Field(default=60, alias="RERANKER_TIMEOUT_SECONDS")

    llm_base_url: str = Field(default="http://127.0.0.1:8004/v1", alias="LLM_BASE_URL")
    llm_model: str = Field(default="Qwen3.6-27B-GGUF:Q4_K_M", alias="LLM_MODEL")
    llm_timeout_seconds: float = Field(default=120, alias="LLM_TIMEOUT_SECONDS")
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2048, alias="LLM_MAX_TOKENS")

    chunk_target_chars: int = Field(default=800, alias="CHUNK_TARGET_CHARS")
    chunk_max_chars: int = Field(default=1400, alias="CHUNK_MAX_CHARS")
    chunk_overlap_chars: int = Field(default=100, alias="CHUNK_OVERLAP_CHARS")

    retrieval_top_k: int = Field(default=50, alias="RETRIEVAL_TOP_K")
    rerank_top_n: int = Field(default=8, alias="RERANK_TOP_N")
    llm_context_top_n: int = Field(default=8, alias="LLM_CONTEXT_TOP_N")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("embedding_dim")
    @classmethod
    def validate_embedding_dim(cls, value: int) -> int:
        if value != 1024:
            raise ValueError("bge-m3 dense embedding dimension must be 1024")
        return value

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator(
        "embedding_base_url",
        "feishu_base_url",
        "milvus_uri",
        "reranker_base_url",
        "llm_base_url",
    )
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("service URL must start with http:// or https://")
        return value.rstrip("/")

    @property
    def feishu_credentials_configured(self) -> bool:
        return bool(self.feishu_app_id and self.feishu_app_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
