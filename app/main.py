"""FastAPI application factory and entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.container import Container
from app.core.config.settings import get_settings
from app.core.logging.setup import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events for the FastAPI application.
    Initializes and cleans up infrastructure resources.
    """
    logger = get_logger("app.main")
    container: Container = app.state.container  # type: ignore[attr-defined]
    settings = container.settings()

    logger.info("Application starting", app_name=app.title, version=app.version)

    # ── Startup ──────────────────────────────────
    # Ensure Qdrant collection exists
    vector_repo = container.vector_repository()
    await vector_repo.ensure_collection(
        collection_name=settings.qdrant.collection_name,
        vector_size=settings.openai.embedding_dimensions,
    )

    # Start background worker
    worker = container.background_worker()
    await worker.start()

    logger.info(
        "Infrastructure initialized",
        qdrant_collection=settings.qdrant.collection_name,
        redis_url=settings.redis.url.split("@")[-1] if "@" in settings.redis.url else settings.redis.url,
    )

    yield

    # ── Shutdown ──────────────────────────────────
    logger.info("Application shutting down")

    # Stop background worker
    await worker.stop()

    # Close Redis connection
    redis_cache = container.redis_cache()
    await redis_cache.close()

    # Close Qdrant client
    await vector_repo.close()
from fastapi import FastAPI
from starlette.responses import JSONResponse

from app.api.middleware.error_handler import register_exception_handlers
from app.api.middleware.rate_limit import create_rate_limit_middleware
from app.api.middleware.request_logging import request_logging_middleware
from app.api.routers import api_router
from app.container import Container
from app.core.config.settings import get_settings
from app.core.logging.setup import configure_logging, get_logger

logger = get_logger(__name__)

# [lifespan definition remains unchanged above this point]

def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    # Configure structured logging
    configure_logging(
        log_level=settings.log_level,
        debug=settings.debug,
    )

    logger = get_logger("app.main")

    # Create DI container
    container = Container()

    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Production-grade AI Backend API with RAG capabilities",
        lifespan=lifespan,
    )

    # Store container on app state for access in dependencies
    app.state.container = container  # type: ignore[attr-defined]

    # Wire container to modules
    container.wire(modules=["app.main"])

    # ──────────────────────────────────────────────
    # Exception Handlers
    # ──────────────────────────────────────────────
    register_exception_handlers(app)

    # ──────────────────────────────────────────────
    # Middleware
    # ──────────────────────────────────────────────
    # Starlette executes middleware in reverse order of addition.
    # We want Logging wrapping Rate Limiting wrapping Routers.
    # Therefore we add Rate Limiting first, then Logging.

    # 1. Rate Limiting (inner)
    rate_limiter = container.rate_limiter()
    app.middleware("http")(create_rate_limit_middleware(rate_limiter))

    # 2. Request Logging (outer)
    app.middleware("http")(request_logging_middleware)

    # ──────────────────────────────────────────────
    # Routers
    # ──────────────────────────────────────────────
    app.include_router(api_router)

    # ──────────────────────────────────────────────
    # Health check endpoint
    # ──────────────────────────────────────────────

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": "0.1.0",
            "app_name": settings.app_name,
        }

    logger.info(
        "Application configured",
        debug=settings.debug,
        log_level=settings.log_level,
    )

    return app


# Application instance for uvicorn: `uvicorn app.main:app`
app = create_app()
