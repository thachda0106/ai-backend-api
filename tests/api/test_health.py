"""API endpoint tests — health check and document ingestion.

Uses FastAPI's TestClient (synchronous in-process HTTP client).
External dependencies (Redis, Qdrant) are intercepted via DI overrides.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# Provide minimal env vars before importing the app so Settings validation passes
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("API_KEY", "test-api-key-123456")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create a TestClient that bypasses the lifespan (no real infra needed)."""
    from app.main import create_app  # type: ignore

    app = create_app()

    # Override DI container to avoid real connections at test time
    container = app.state.container  # type: ignore[attr-defined]

    # Mock Redis cache
    mock_cache = MagicMock()
    mock_cache.close = AsyncMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()
    container.redis_cache.override(mock_cache)  # type: ignore[attr-defined]

    # Mock rate limiter (allow all)
    mock_rate_limiter = MagicMock()
    mock_rate_limiter.is_allowed = AsyncMock(return_value=True)
    container.rate_limiter.override(mock_rate_limiter)  # type: ignore[attr-defined]

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


class TestHealthEndpoint:
    def test_health_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_has_status_field(self, client: TestClient) -> None:
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_response_has_version(self, client: TestClient) -> None:
        response = client.get("/health")
        data = response.json()
        assert "version" in data
