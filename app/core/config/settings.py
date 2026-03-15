"""Application settings using pydantic-settings v2 with nested models."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field, SecretStr
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


class QdrantSettings(BaseModel):
    """Qdrant vector database configuration."""

    host: str = "localhost"
    port: int = 6333
    grpc_port: int = 6334
    collection_name: str = "documents"
    prefer_grpc: bool = True


class ChunkingSettings(BaseModel):
    """Document chunking configuration."""

    chunk_size: int = Field(default=512, ge=100, le=8192)
    chunk_overlap: int = Field(default=50, ge=0, le=512)
    separator: str = "\n"


class RateLimitSettings(BaseModel):
    """Rate limiting configuration."""

    requests_per_minute: int = Field(default=60, ge=1)
    burst_size: int = Field(default=10, ge=1)


class Settings(BaseSettings):
    """Application settings with nested configuration groups.

    Environment variables use __ as delimiter for nested fields.
    Example: OPENAI__API_KEY=sk-... maps to settings.openai.api_key
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

    # API Authentication
    api_key: SecretStr = SecretStr("change-me-in-production")

    # Nested settings groups
    openai: OpenAISettings
    redis: RedisSettings = Field(default_factory=RedisSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)

    def to_safe_dict(self) -> dict[str, Any]:
        """Return settings as dict with secrets masked."""
        data = self.model_dump()
        data["api_key"] = "***"
        data["openai"]["api_key"] = "***"
        if data["redis"].get("password"):
            data["redis"]["password"] = "***"
        return data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached singleton settings instance.

    Settings are loaded once and cached for the lifetime of the process.
    """
    return Settings()  # type: ignore[call-arg]
