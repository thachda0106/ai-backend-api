"""Asyncio-based background worker.

Lightweight in-process task queue using asyncio primitives.
Supports enqueue, concurrency limiting, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Coroutine
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class TaskStatus(str, Enum):
    """Status of a background task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackgroundWorker:
    """Asyncio-based background task queue.

    Uses asyncio.Queue for scheduling and asyncio.Semaphore
    for concurrency control. Tracks task status for observability.
    """

    def __init__(self, max_concurrent: int = 5) -> None:
        self._queue: asyncio.Queue[tuple[str, Coroutine[Any, Any, Any]]] = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._tasks: dict[str, dict[str, Any]] = {}
        self._running = False
        self._worker_task: asyncio.Task[None] | None = None

    async def enqueue(
        self,
        coro: Coroutine[Any, Any, Any],
        task_name: str = "",
    ) -> str:
        """Enqueue a coroutine for background execution.

        Args:
            coro: The coroutine to execute.
            task_name: Optional name for observability.

        Returns:
            A unique task ID.
        """
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {
            "status": TaskStatus.PENDING,
            "name": task_name,
            "error": None,
        }
        await self._queue.put((task_id, coro))

        await logger.ainfo(
            "task_enqueued",
            task_id=task_id,
            task_name=task_name,
            queue_size=self._queue.qsize(),
        )
        return task_id

    async def start(self) -> None:
        """Start the worker loop."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        await logger.ainfo("background_worker_started")

    async def stop(self) -> None:
        """Gracefully stop the worker.

        Waits for currently running tasks to complete,
        cancels pending tasks in the queue.
        """
        self._running = False

        # Cancel pending tasks in queue
        cancelled = 0
        while not self._queue.empty():
            try:
                task_id, coro = self._queue.get_nowait()
                self._tasks[task_id]["status"] = TaskStatus.CANCELLED
                coro.close()  # Properly close the unawaited coroutine
                cancelled += 1
            except asyncio.QueueEmpty:
                break

        # Cancel the worker loop
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        completed = sum(
            1 for t in self._tasks.values() if t["status"] == TaskStatus.COMPLETED
        )
        failed = sum(
            1 for t in self._tasks.values() if t["status"] == TaskStatus.FAILED
        )

        await logger.ainfo(
            "background_worker_stopped",
            completed=completed,
            failed=failed,
            cancelled=cancelled,
        )

    async def get_status(self, task_id: str) -> dict[str, Any]:
        """Get the status of a background task.

        Args:
            task_id: The task ID returned by enqueue().

        Returns:
            Dict with status, name, and error (if failed).
        """
        if task_id not in self._tasks:
            return {"status": "unknown", "name": "", "error": None}
        return dict(self._tasks[task_id])

    async def _worker_loop(self) -> None:
        """Main worker loop — processes tasks from the queue."""
        while self._running:
            try:
                task_id, coro = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
                asyncio.create_task(self._execute(task_id, coro))
            except asyncio.TimeoutError:
                continue  # Check if still running
            except asyncio.CancelledError:
                break

    async def _execute(self, task_id: str, coro: Coroutine[Any, Any, Any]) -> None:
        """Execute a single task with concurrency control."""
        async with self._semaphore:
            self._tasks[task_id]["status"] = TaskStatus.RUNNING
            await logger.ainfo(
                "task_started",
                task_id=task_id,
                task_name=self._tasks[task_id]["name"],
            )

            try:
                await coro
                self._tasks[task_id]["status"] = TaskStatus.COMPLETED
                await logger.ainfo(
                    "task_completed",
                    task_id=task_id,
                    task_name=self._tasks[task_id]["name"],
                )
            except Exception as exc:
                self._tasks[task_id]["status"] = TaskStatus.FAILED
                self._tasks[task_id]["error"] = str(exc)
                await logger.aerror(
                    "task_failed",
                    task_id=task_id,
                    task_name=self._tasks[task_id]["name"],
                    error=str(exc),
                )
