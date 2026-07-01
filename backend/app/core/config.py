import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class FeishuAccountConfig:
    account_id: str
    tenant_name: str
    app_id: str
    app_secret: str
    enabled: bool = True

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_secret)

    def public_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "tenant_name": self.tenant_name,
            "enabled": self.enabled,
            "configured": self.configured,
        }


class Settings(BaseSettings):
    app_env: str = Field(default="local", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=3301, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_allow_origins: list[str] = Field(
        default=[
            "http://127.0.0.1:3300",
            "http://localhost:3300",
        ],
        alias="CORS_ALLOW_ORIGINS",
    )

    sqlite_path: Path = Field(
        default=Path("data/state/feishu_rag.sqlite3"),
        alias="SQLITE_PATH",
    )

    feishu_base_url: str = Field(default="https://open.feishu.cn", alias="FEISHU_BASE_URL")
    feishu_app_id: str | None = Field(default=None, alias="FEISHU_APP_ID")
    feishu_app_secret: str | None = Field(default=None, alias="FEISHU_APP_SECRET")
    feishu_accounts_json: str | None = Field(default=None, alias="FEISHU_ACCOUNTS_JSON")
    feishu_request_timeout_seconds: float = Field(
        default=30, alias="FEISHU_REQUEST_TIMEOUT_SECONDS"
    )
    feishu_page_size: int = Field(default=50, alias="FEISHU_PAGE_SIZE")

    embedding_base_url: str = Field(default="http://127.0.0.1:8010", alias="EMBEDDING_BASE_URL")
    embedding_model: str = Field(default="BAAI/bge-m3", alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(default=1024, alias="EMBEDDING_DIM")
    embedding_timeout_seconds: float = Field(default=60, alias="EMBEDDING_TIMEOUT_SECONDS")

    milvus_uri: str = Field(default="http://127.0.0.1:19530", alias="MILVUS_URI")
    milvus_db: str = Field(default="default", alias="MILVUS_DB")
    milvus_collection: str = Field(default="feishu_chunks_v2", alias="MILVUS_COLLECTION")
    milvus_legacy_collection: str | None = Field(
        default="feishu_chunks_v1", alias="MILVUS_LEGACY_COLLECTION"
    )
    milvus_timeout_seconds: float = Field(default=5, alias="MILVUS_TIMEOUT_SECONDS")

    reranker_base_url: str = Field(default="http://127.0.0.1:8020", alias="RERANKER_BASE_URL")
    reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3", alias="RERANKER_MODEL")
    reranker_timeout_seconds: float = Field(default=60, alias="RERANKER_TIMEOUT_SECONDS")

    llm_base_url: str = Field(default="http://127.0.0.1:8040/v1", alias="LLM_BASE_URL")
    llm_model: str = Field(default="gemma-4-12b-it-qat-q4_0", alias="LLM_MODEL")
    llm_timeout_seconds: float = Field(default=120, alias="LLM_TIMEOUT_SECONDS")
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2048, alias="LLM_MAX_TOKENS")

    chunk_target_chars: int = Field(default=800, alias="CHUNK_TARGET_CHARS")
    chunk_max_chars: int = Field(default=1400, alias="CHUNK_MAX_CHARS")
    chunk_overlap_chars: int = Field(default=100, alias="CHUNK_OVERLAP_CHARS")

    retrieval_top_k: int = Field(default=50, alias="RETRIEVAL_TOP_K")
    rerank_top_n: int = Field(default=8, alias="RERANK_TOP_N")
    llm_context_top_n: int = Field(default=8, alias="LLM_CONTEXT_TOP_N")

    weekly_scan_enabled: bool = Field(default=True, alias="WEEKLY_SCAN_ENABLED")
    weekly_scan_day: str = Field(default="SUN", alias="WEEKLY_SCAN_DAY")
    weekly_scan_time: str = Field(default="03:00", alias="WEEKLY_SCAN_TIME")
    weekly_scan_timezone: str = Field(
        default="Asia/Shanghai", alias="WEEKLY_SCAN_TIMEZONE"
    )

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

    @field_validator("milvus_collection")
    @classmethod
    def upgrade_legacy_milvus_collection(cls, value: str) -> str:
        if value == "feishu_chunks_v1":
            return "feishu_chunks_v2"
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
        return any(account.enabled and account.configured for account in self.feishu_accounts)

    @property
    def feishu_accounts(self) -> list[FeishuAccountConfig]:
        if self.feishu_accounts_json:
            raw_accounts = self._parse_feishu_accounts_json(self.feishu_accounts_json)
            return [self._normalize_feishu_account(item) for item in raw_accounts]
        return [
            FeishuAccountConfig(
                account_id="default",
                tenant_name="当前企业",
                app_id=self.feishu_app_id or "",
                app_secret=self.feishu_app_secret or "",
                enabled=True,
            )
        ]

    @property
    def enabled_feishu_accounts(self) -> list[FeishuAccountConfig]:
        return [account for account in self.feishu_accounts if account.enabled]

    @property
    def public_feishu_accounts(self) -> list[dict[str, Any]]:
        return [account.public_dict() for account in self.feishu_accounts]

    def get_feishu_account(self, account_id: str) -> FeishuAccountConfig | None:
        for account in self.feishu_accounts:
            if account.account_id == account_id:
                return account
        return None

    @staticmethod
    def _parse_feishu_accounts_json(value: str) -> list[dict[str, Any]]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("FEISHU_ACCOUNTS_JSON must be valid JSON") from exc
        if not isinstance(parsed, list):
            raise ValueError("FEISHU_ACCOUNTS_JSON must be a JSON array")
        if not all(isinstance(item, dict) for item in parsed):
            raise ValueError("FEISHU_ACCOUNTS_JSON items must be JSON objects")
        return parsed

    @staticmethod
    def _normalize_feishu_account(raw: dict[str, Any]) -> FeishuAccountConfig:
        account_id = str(raw.get("account_id") or "").strip()
        if not account_id:
            raise ValueError("Feishu account account_id is required")
        return FeishuAccountConfig(
            account_id=account_id,
            tenant_name=str(raw.get("tenant_name") or account_id),
            app_id=str(raw.get("app_id") or ""),
            app_secret=str(raw.get("app_secret") or ""),
            enabled=bool(raw.get("enabled", True)),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
