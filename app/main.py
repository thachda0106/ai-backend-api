"""FastAPI application factory and entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.middleware.error_handler import register_exception_handlers
from app.api.middleware.rate_limit import create_rate_limit_middleware
from app.api.middleware.request_logging import request_logging_middleware
from app.api.routers import api_router
from app.container import Container
from app.core.config.settings import get_settings
from app.core.logging.setup import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown lifecycle."""
    logger = get_logger("app.main")
    container: Container = app.state.container  # type: ignore[attr-defined]
    settings = container.settings()

    logger.info("Application starting", app_name=app.title, version=app.version)

    # ── Startup ────────────────────────────────────────────────────────────
    # Connect PostgreSQL pool
    db_pool = container.postgres_pool()
    await db_pool.connect()

    # Ensure Qdrant collection and indexes exist
    vector_repo = container.vector_repository()
    await vector_repo.ensure_collection(
        collection_name=settings.qdrant.collection_name,
        vector_size=settings.openai.embedding_dimensions,
    )

    logger.info(
        "Infrastructure initialized",
        qdrant_collection=settings.qdrant.collection_name,
        postgres_host=settings.database.host,
    )

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────
    logger.info("Application shutting down")

    await db_pool.close()

    redis_cache = container.redis_cache()
    await redis_cache.close()

    await vector_repo.close()

    # Close ARQ pool
    arq_pool = container.arq_pool()
    await arq_pool.aclose()

    logger.info("Application stopped cleanly")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    configure_logging(log_level=settings.log_level, debug=settings.debug)

    logger = get_logger("app.main")

    container = Container()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Production-grade multi-tenant AI Backend API with RAG capabilities",
        lifespan=lifespan,
    )

    app.state.container = container  # type: ignore[attr-defined]
    container.wire(modules=["app.main"])

    # Exception handlers
    register_exception_handlers(app)

    # Middleware (Starlette executes in reverse add order)
    rate_limiter = container.rate_limiter()
    app.middleware("http")(create_rate_limit_middleware(rate_limiter))
    app.middleware("http")(request_logging_middleware)

    # API routers
    app.include_router(api_router)

    # ── Health Check (IMP-8 Fix: deep check, not trivial 200) ─────────────
    @app.get("/health", tags=["health"])
    async def health_check() -> JSONResponse:
        """Deep health check — pings all dependencies.

        Returns 200 if all dependencies are reachable.
        Returns 503 if any dependency is unhealthy.
        """
        checks: dict[str, str] = {}
        healthy = True

        # Redis check
        try:
            redis = container.redis_cache()
            await redis.client.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"
            healthy = False

        # Qdrant check
        try:
            qdrant = container.vector_repository()
            await qdrant.client.get_collections()
            checks["qdrant"] = "ok"
        except Exception as exc:
            checks["qdrant"] = f"error: {exc}"
            healthy = False

        # PostgreSQL check
        try:
            db = container.postgres_pool()
            await db.fetchval("SELECT 1")
            checks["postgres"] = "ok"
        except Exception as exc:
            checks["postgres"] = f"error: {exc}"
            healthy = False

        status = "healthy" if healthy else "degraded"
        http_status = 200 if healthy else 503

        return JSONResponse(
            content={
                "status": status,
                "version": "1.0.0",
                "app_name": settings.app_name,
                "checks": checks,
            },
            status_code=http_status,
        )

    logger.info("Application configured", debug=settings.debug, log_level=settings.log_level)

    return app


# Application instance for uvicorn: `uvicorn app.main:app`
app = create_app()
