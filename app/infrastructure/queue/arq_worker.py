"""ARQ-based background worker for document processing.

Replaces the in-memory asyncio.Queue with a Redis-backed ARQ queue.
This enables:
  - Job persistence across restarts
  - Multiple worker replicas
  - Automatic retry with exponential backoff
  - Dead-letter tracking via a Redis sorted set

Usage (standalone worker process):
    arq app.infrastructure.queue.arq_worker.ArqWorkerSettings
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import structlog
from arq import create_pool
from arq.connections import RedisSettings as ArqRedisSettings

from app.core.config.settings import get_settings

logger = structlog.get_logger(__name__)

# Dead-letter queue key in Redis
_DLQ_KEY = "dlq:document_processing"


# ── Task Functions ─────────────────────────────────────────────────────────


async def process_document_task(
    ctx: dict[str, Any],
    tenant_id: str,
    document_id: str,
    job_id: str,
) -> dict[str, Any]:
    """ARQ task: run the full document processing pipeline.

    This is the ARQ task function. It rebuilds necessary use-case
    objects from the shared container stored in ctx.

    Args:
        ctx:         ARQ worker context (contains 'container').
        tenant_id:   String UUID of the owning tenant.
        document_id: String UUID of the document to process.
        job_id:      String UUID of the IngestionJob tracking this run.

    Returns:
        Dict with processing result metrics.
    """
    from app.domain.entities.ingestion_job import IngestionJob, IngestionStatus
    from app.domain.value_objects.identifiers import DocumentId, IngestionJobId
    from app.domain.value_objects.tenant_id import TenantId

    container = ctx["container"]
    start_time = time.monotonic()

    doc_id = DocumentId.from_str(document_id)
    t_id = TenantId.from_str(tenant_id)

    # Reconstruct the IngestionJob from the serialized job_id
    # (job state lives in ARQ redis; we recreate a fresh FSM object)
    ingestion_job = IngestionJob(
        job_id=IngestionJobId.from_str(job_id),
        document_id=doc_id,
    )

    await logger.ainfo(
        "arq_task_started",
        tenant_id=tenant_id,
        document_id=document_id,
        job_id=job_id,
        attempt=ctx.get("job_try", 1),
    )

    try:
        process_use_case = container.process_document()
        await process_use_case.execute(doc_id, ingestion_job, tenant_id=t_id)

        elapsed = time.monotonic() - start_time
        await logger.ainfo(
            "arq_task_completed",
            tenant_id=tenant_id,
            document_id=document_id,
            elapsed_seconds=round(elapsed, 3),
        )
        return {
            "document_id": document_id,
            "status": "completed",
            "elapsed_seconds": round(elapsed, 3),
        }

    except Exception as exc:
        elapsed = time.monotonic() - start_time
        attempt = ctx.get("job_try", 1)
        settings = get_settings()

        await logger.aerror(
            "arq_task_failed",
            tenant_id=tenant_id,
            document_id=document_id,
            attempt=attempt,
            max_retries=settings.worker.max_retries,
            error=str(exc),
            elapsed_seconds=round(elapsed, 3),
        )

        # On final retry, write to Dead Letter Queue
        if attempt >= settings.worker.max_retries:
            await _write_to_dlq(ctx, tenant_id, document_id, job_id, str(exc))

        raise  # Let ARQ handle retry scheduling


async def _write_to_dlq(
    ctx: dict[str, Any],
    tenant_id: str,
    document_id: str,
    job_id: str,
    error: str,
) -> None:
    """Write a failed job to the Dead Letter Queue sorted set in Redis."""
    try:
        redis = ctx["redis"]
        entry = json.dumps({
            "tenant_id": tenant_id,
            "document_id": document_id,
            "job_id": job_id,
            "error": error,
            "failed_at": time.time(),
        })
        await redis.zadd(_DLQ_KEY, {entry: time.time()})
        await logger.awarning(
            "job_sent_to_dlq",
            document_id=document_id,
            dlq_key=_DLQ_KEY,
        )
    except Exception as dlq_exc:
        await logger.aerror("dlq_write_failed", error=str(dlq_exc))


# ── Worker Startup / Shutdown Hooks ────────────────────────────────────────


async def startup(ctx: dict[str, Any]) -> None:
    """Initialize shared resources for the worker process."""
    from app.container import Container
    from app.core.logging.setup import configure_logging

    settings = get_settings()
    configure_logging(log_level=settings.log_level, debug=settings.debug)

    container = Container()

    # Connect PostgreSQL pool
    db_pool = container.postgres_pool()
    await db_pool.connect()

    # Store in context for task functions to reuse
    ctx["container"] = container

    await logger.ainfo("arq_worker_started", max_jobs=settings.worker.max_jobs)


async def shutdown(ctx: dict[str, Any]) -> None:
    """Gracefully close shared resources."""
    container = ctx.get("container")
    if container:
        db_pool = container.postgres_pool()
        await db_pool.close()

        redis_cache = container.redis_cache()
        await redis_cache.close()

        vector_repo = container.vector_repository()
        await vector_repo.close()

    await logger.ainfo("arq_worker_stopped")


# ── ARQ WorkerSettings ─────────────────────────────────────────────────────


class ArqWorkerSettings:
    """ARQ worker configuration class.

    Run with: arq app.infrastructure.queue.arq_worker.ArqWorkerSettings
    """

    _settings = get_settings()

    functions = [process_document_task]
    on_startup = startup
    on_shutdown = shutdown

    redis_settings = ArqRedisSettings(
        host=_settings.redis.host,
        port=_settings.redis.port,
        password=(
            _settings.redis.password.get_secret_value()
            if _settings.redis.password
            else None
        ),
        database=_settings.redis.db,
    )

    max_jobs = _settings.worker.max_jobs
    job_timeout = _settings.worker.job_timeout
    max_tries = _settings.worker.max_retries
    poll_delay = 0.5  # seconds between queue polls
    queue_read_limit = 10
