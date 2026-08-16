"""Typed application configuration loaded from environment variables.

Secrets are represented as Pydantic ``SecretStr`` values so accidental logging
or printing does not expose them. The checked-in ``.env.example`` documents all
available settings; real values belong only in a local ``.env`` file or secret
manager.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from eci.exceptions import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings with cross-field safety validation."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Enterprise Complaint Intelligence Platform"
    app_version: str = "1.0.0"
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'eci_demo.db').as_posix()}"
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_pool_recycle_seconds: int = Field(default=1800, ge=60)

    vector_backend: Literal["local", "weaviate"] = "local"
    vector_index_path: Path = PROJECT_ROOT / "data" / "vector" / "local_index.json"
    weaviate_mode: Literal["local", "cloud"] = "local"
    weaviate_url: str = "http://localhost:8080"
    weaviate_api_key: SecretStr | None = None
    weaviate_collection: str = "ComplaintNarrative"

    embedding_backend: Literal["local", "openai"] = "local"
    answer_backend: Literal["local", "openai"] = "local"
    local_embedding_dimensions: int = Field(default=1024, ge=64, le=4096)
    openai_api_key: SecretStr | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-5.6-luna"
    openai_timeout_seconds: float = Field(default=30.0, ge=5.0, le=120.0)
    openai_max_retries: int = Field(default=3, ge=0, le=8)

    hmac_secret: SecretStr = SecretStr(
        "demo-only-change-this-secret-before-using-real-data-123456"
    )
    pii_redaction_enabled: bool = True
    store_rejected_rows_in_database: bool = True
    audit_user_queries: bool = False

    max_input_file_mb: int = Field(default=25, ge=1, le=1024)
    max_input_rows: int = Field(default=100_000, ge=1, le=10_000_000)
    max_query_characters: int = Field(default=500, ge=50, le=4000)
    default_top_k: int = Field(default=5, ge=1, le=20)
    max_top_k: int = Field(default=10, ge=1, le=50)
    max_context_characters: int = Field(default=24000, ge=2000, le=100000)
    rate_limit_requests: int = Field(default=20, ge=1, le=1000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)

    raw_data_dir: Path = PROJECT_ROOT / "data" / "raw"
    processed_data_dir: Path = PROJECT_ROOT / "data" / "processed"
    rejected_data_dir: Path = PROJECT_ROOT / "data" / "rejected"
    log_dir: Path = PROJECT_ROOT / "logs"

    @field_validator("weaviate_url")
    @classmethod
    def normalize_weaviate_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @field_validator("weaviate_collection")
    @classmethod
    def validate_collection_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or not cleaned[0].isupper() or not cleaned.replace("_", "").isalnum():
            raise ValueError(
                "WEAVIATE_COLLECTION must begin with an uppercase letter and contain only letters, numbers, or underscores"
            )
        return cleaned

    @model_validator(mode="after")
    def validate_backend_requirements(self) -> "Settings":
        if self.embedding_backend == "openai" or self.answer_backend == "openai":
            if self.openai_api_key is None or not self.openai_api_key.get_secret_value().strip():
                raise ConfigurationError(
                    "OPENAI_API_KEY is required when EMBEDDING_BACKEND or ANSWER_BACKEND is 'openai'."
                )

        if self.vector_backend == "weaviate":
            if not self.weaviate_url:
                raise ConfigurationError("WEAVIATE_URL is required for the Weaviate backend.")
            if self.weaviate_api_key is None or not self.weaviate_api_key.get_secret_value().strip():
                raise ConfigurationError(
                    "WEAVIATE_API_KEY is required for the secured Weaviate backend."
                )

        if self.default_top_k > self.max_top_k:
            raise ConfigurationError("DEFAULT_TOP_K cannot exceed MAX_TOP_K.")

        if self.environment == "production":
            secret = self.hmac_secret.get_secret_value()
            if "demo-only" in secret or len(secret) < 32:
                raise ConfigurationError(
                    "Production requires a unique HMAC_SECRET of at least 32 characters."
                )
        return self

    def ensure_directories(self) -> None:
        """Create runtime directories without touching secret files."""
        for path in (
            self.raw_data_dir,
            self.processed_data_dir,
            self.rejected_data_dir,
            self.vector_index_path.parent,
            self.log_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    @property
    def database_dialect(self) -> str:
        driver_name = self.database_url.split(":", maxsplit=1)[0].lower()
        return driver_name.split("+", maxsplit=1)[0]

    @property
    def is_sqlite(self) -> bool:
        return self.database_dialect == "sqlite"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings


def clear_settings_cache() -> None:
    """Used by tests and configuration-switching scripts."""
    get_settings.cache_clear()
