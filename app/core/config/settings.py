"""Application settings using pydantic-settings v2 with nested models."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenAISettings(BaseModel):
    """OpenAI API configuration."""

    api_key: SecretStr
    model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    max_retries: int = 3
    embedding_dimensions: int = 1536
    max_tokens: int = 4096
    temperature: float = 0.7


class RedisSettings(BaseModel):
    """Redis connection configuration."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: SecretStr | None = None

    @property
    def url(self) -> str:
        """Build Redis connection URL."""
        if self.password:
            return f"redis://:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class DatabaseSettings(BaseModel):
    """PostgreSQL connection configuration."""

    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: SecretStr = SecretStr("postgres")
    db_name: str = "ai_backend"
    pool_min_size: int = 2
    pool_max_size: int = 10

    @property
    def url(self) -> str:
        """Build asyncpg DSN."""
        pw = self.password.get_secret_value()
        return f"postgresql://{self.user}:{pw}@{self.host}:{self.port}/{self.db_name}"


class QdrantSettings(BaseModel):
    """Qdrant vector database configuration."""

    host: str = "localhost"
    port: int = 6333
    grpc_port: int = 6334
    collection_name: str = "documents"
    prefer_grpc: bool = True


class ChunkingSettings(BaseModel):
    """Document chunking configuration (in tokens, not characters)."""

    chunk_size: int = Field(default=512, ge=100, le=8192)
    chunk_overlap: int = Field(default=50, ge=0, le=512)


class RateLimitSettings(BaseModel):
    """Rate limiting configuration."""

    requests_per_minute: int = Field(default=60, ge=1)
    burst_size: int = Field(default=10, ge=1)


class WorkerSettings(BaseModel):
    """ARQ background worker configuration."""

    max_jobs: int = 10
    job_timeout: int = 300  # seconds per job
    max_retries: int = 3
    retry_delay: int = 30  # seconds between retries


class RAGSettings(BaseModel):
    """RAG pipeline quality configuration."""

    score_threshold: float = Field(default=0.72, ge=0.0, le=1.0)
    max_context_tokens: int = Field(default=20_000, ge=1000)
    top_k: int = Field(default=10, ge=1, le=50)


class Settings(BaseSettings):
    """Application settings with nested configuration groups.

    Environment variables use __ as delimiter for nested fields.
    Example:
        OPENAI__API_KEY=sk-...      → settings.openai.api_key
        DATABASE__HOST=db           → settings.database.host
        RAG__SCORE_THRESHOLD=0.8    → settings.rag.score_threshold
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        env_ignore_empty=True,
        case_sensitive=False,
    )

    # Application
    app_name: str = "AI Backend API"
    debug: bool = False
    log_level: str = "INFO"

    # API Authentication (master/admin key — tenants have their own keys in DB)
    api_key: SecretStr = SecretStr("change-me-in-production")

    # Nested settings groups
    openai: OpenAISettings
    redis: RedisSettings = Field(default_factory=RedisSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        """Reject sentinel API key in production (non-debug) mode."""
        sentinel = "change-me-in-production"
        if not self.debug and self.api_key.get_secret_value() == sentinel:
            msg = (
                "API_KEY must be set to a secure value in production. "
                "Set DEBUG=true to bypass this check during development."
            )
            raise ValueError(msg)
        return self

    def to_safe_dict(self) -> dict[str, Any]:
        """Return settings as dict with secrets masked."""
        data = self.model_dump()
        data["api_key"] = "***"
        data["openai"]["api_key"] = "***"
        if data["redis"].get("password"):
            data["redis"]["password"] = "***"
        if data["database"].get("password"):
            data["database"]["password"] = "***"
        return data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached singleton settings instance."""
    return Settings()  # type: ignore[call-arg]
