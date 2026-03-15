---
phase: 2
plan: 6
wave: 3
depends_on: ["2.1", "2.2", "2.3", "2.4", "2.5"]
files_modified:
  - app/infrastructure/queue/worker.py
  - app/container.py
  - app/main.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Background worker can enqueue and execute async tasks"
    - "DI container wires all concrete implementations"
    - "Container dependency stubs replaced with Singleton/Factory providers"
    - "FastAPI lifespan initializes and shuts down all resources"
---

# Plan 2.6: Background Worker + Container Wiring

## Objective
Implement the asyncio-based background worker for async document processing and wire ALL Phase 2 infrastructure into the DI container. This is the composition root — after this plan, the full infrastructure stack is operational.

## Context
- @app/container.py — Current container with Dependency stubs
- @app/main.py — FastAPI app factory with lifespan
- @app/core/config/settings.py — All settings groups
- All Phase 2 infrastructure modules created in plans 2.1-2.5

## Tasks

<task type="auto">
  <name>Implement asyncio background worker</name>
  <files>app/infrastructure/queue/worker.py</files>
  <action>
    Implement `BackgroundWorker`:
    
    1. `__init__(self, max_concurrent: int = 5)`:
       - Create asyncio.Queue for tasks
       - Track running tasks with asyncio.TaskGroup or set
    
    2. `async def enqueue(self, coro: Coroutine, task_name: str = "") -> str`:
       - Add a coroutine to the queue
       - Return a task ID (UUID)
       - Log enqueue with structlog
    
    3. `async def start(self) -> None`:
       - Start worker loop that processes tasks from the queue
       - Respect max_concurrent limit using asyncio.Semaphore
    
    4. `async def stop(self) -> None`:
       - Graceful shutdown: wait for running tasks, cancel pending
       - Log shutdown with count of completed/cancelled tasks
    
    5. `async def get_status(self, task_id: str) -> dict`:
       - Return status of a task (pending, running, completed, failed)
    
    Keep it simple — this is a lightweight in-process task queue,
    not a distributed system. Use asyncio primitives only.
  </action>
  <verify>python -m poetry run python -c "from app.infrastructure.queue.worker import BackgroundWorker; print('OK')"</verify>
  <done>BackgroundWorker with enqueue/start/stop and task status tracking</done>
</task>

<task type="auto">
  <name>Wire all infrastructure into DI container and update lifespan</name>
  <files>app/container.py, app/main.py</files>
  <action>
    Update `app/container.py`:
    
    Replace Dependency stubs with concrete providers:
    
    ```
    # Infrastructure - Singletons (long-lived)
    redis_cache = providers.Singleton(RedisCache, url=settings.provided.redis.url)
    rate_limiter = providers.Singleton(RedisRateLimiter, redis_cache=redis_cache, ...)
    background_worker = providers.Singleton(BackgroundWorker)
    
    # LLM - Singletons
    embedding_provider = providers.Singleton(OpenAIEmbeddingService, settings=settings.provided.openai)
    chat_provider = providers.Singleton(OpenAIChatService, settings=settings.provided.openai)
    
    # Domain Services - Singletons
    token_service = providers.Singleton(TiktokenService)  # Override Dependency stub
    
    # Infrastructure Adapters - Singletons
    vector_repository = providers.Singleton(QdrantVectorRepository, settings=settings.provided.qdrant)
    document_repository = providers.Singleton(InMemoryDocumentRepository)
    chunk_repository = providers.Singleton(InMemoryChunkRepository)
    chat_history_repository = providers.Singleton(RedisChatHistoryRepository, redis_cache=redis_cache)
    ```
    
    Update `app/main.py` lifespan:
    - Startup: initialize Redis connection, ensure Qdrant collection, start background worker
    - Shutdown: stop background worker, close Redis connection
    
    Update wiring_config to include new modules.
    
    IMPORTANT: When wiring settings properties to providers, use `settings.provided.redis` syntax
    from dependency-injector to access nested attributes lazily.
  </action>
  <verify>python -m poetry run python -c "from app.container import Container; c = Container(); print(f'Providers: {list(c.providers.keys())}'); assert 'redis_cache' in c.providers; assert 'embedding_provider' in c.providers; assert 'vector_repository' in c.providers; print('OK')"</verify>
  <done>Container has all concrete providers wired, lifespan manages lifecycle</done>
</task>

## Success Criteria
- [ ] `BackgroundWorker` processes async tasks with concurrency control
- [ ] Container has concrete providers for ALL infrastructure services
- [ ] No more `Dependency` stubs — all replaced with `Singleton`/`Factory`
- [ ] FastAPI lifespan properly initializes and shuts down resources
- [ ] `python -m poetry run python -c "from app.container import Container; Container()"` works
