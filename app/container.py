"""Dependency injection container — the composition root.

This container wires all application layers together using
dependency-injector's DeclarativeContainer. All infrastructure
providers are concrete Singleton/Factory instances.

Changes from original:
  - PostgresPool + PostgresDocumentRepository replacing InMemory (CRIT-2)
  - ARQ pool replacing BackgroundWorker (CRIT-1, CRIT-3)
  - RedisCache injected into OpenAIEmbeddingService (CRIT-4)
  - TokenAwareChunkingStrategy replacing SimpleChunkingStrategy (IMP-2)
  - chunk_size/chunk_overlap from settings (IMP-1)
  - max_context_tokens + score_threshold from settings (IMP-12, IMP-3)
"""

from __future__ import annotations

from dependency_injector import containers, providers

from app.core.config.settings import Settings, get_settings
from app.domain.services.token_aware_chunking import TokenAwareChunkingStrategy

# Infrastructure imports
from app.infrastructure.cache.rate_limiter import RedisRateLimiter
from app.infrastructure.cache.redis_cache import RedisCache
from app.infrastructure.db.postgres_pool import PostgresPool
from app.infrastructure.llm.openai_chat import OpenAIChatService
from app.infrastructure.llm.openai_embedding import OpenAIEmbeddingService
from app.infrastructure.repositories.memory_chunk_repo import InMemoryChunkRepository
from app.infrastructure.repositories.postgres_document_repo import PostgresDocumentRepository
from app.infrastructure.repositories.redis_chat_repo import RedisChatHistoryRepository
from app.infrastructure.token.tiktoken_service import TiktokenService
from app.infrastructure.vector_db.qdrant_adapter import QdrantVectorRepository

# Application layer imports
from app.application.services.context_service import ContextService
from app.application.services.prompt_service import PromptService
from app.application.use_cases.ingest_document import IngestDocumentUseCase
from app.application.use_cases.process_document import ProcessDocumentUseCase
from app.application.use_cases.rag_chat import RAGChatUseCase
from app.application.use_cases.search_documents import SearchDocumentsUseCase



async def _create_arq_pool(redis_url: str) -> object:
    """Resource factory: create an ARQ Redis pool for job enqueueing."""
    from arq import create_pool
    from arq.connections import RedisSettings as ArqRedisSettings

    arq_settings = ArqRedisSettings.from_dsn(redis_url)
    return await create_pool(arq_settings)


class Container(containers.DeclarativeContainer):
    """Application DI container — production wiring.

    Provides:
    - Configuration and settings
    - Domain services (concrete Singletons)
    - Infrastructure adapters (concrete Singletons)
    - Application services (Singletons)
    - Use cases (Factory — new instance per request)
    """

    wiring_config = containers.WiringConfiguration(
        modules=["app.main"],
    )

    # ──────────────────────────────────────────────
    # Configuration
    # ──────────────────────────────────────────────

    settings: providers.Singleton[Settings] = providers.Singleton(get_settings)

    # ──────────────────────────────────────────────
    # Domain Services
    # ──────────────────────────────────────────────

    # IMP-2: Token-aware chunking strategy (tiktoken, not char count)
    chunking_strategy: providers.Singleton[TokenAwareChunkingStrategy] = providers.Singleton(
        TokenAwareChunkingStrategy,
        model=settings.provided.openai.model,
    )

    token_service: providers.Singleton[TiktokenService] = providers.Singleton(
        TiktokenService,
    )

    # ──────────────────────────────────────────────
    # Infrastructure — PostgreSQL (replaces InMemory)
    # ──────────────────────────────────────────────

    postgres_pool: providers.Singleton[PostgresPool] = providers.Singleton(
        PostgresPool,
        settings=settings.provided.database,
    )

    # CRIT-2: PostgreSQL-backed repository (replaces InMemoryDocumentRepository)
    document_repository: providers.Singleton[PostgresDocumentRepository] = providers.Singleton(
        PostgresDocumentRepository,
        pool=postgres_pool,
    )

    # Chunks are only needed in memory during processing; Qdrant is the persistence layer
    chunk_repository: providers.Singleton[InMemoryChunkRepository] = providers.Singleton(
        InMemoryChunkRepository,
    )

    # ──────────────────────────────────────────────
    # Infrastructure — Redis
    # ──────────────────────────────────────────────

    redis_cache: providers.Singleton[RedisCache] = providers.Singleton(
        RedisCache,
        url=settings.provided.redis.url,
    )

    rate_limiter: providers.Singleton[RedisRateLimiter] = providers.Singleton(
        RedisRateLimiter,
        redis_cache=redis_cache,
        requests_per_minute=settings.provided.rate_limit.requests_per_minute,
        burst_size=settings.provided.rate_limit.burst_size,
    )

    # CRIT-1 + CRIT-3: ARQ pool — Redis-backed, survives restarts, multi-worker safe
    # Use providers.Callable so it can be mocked easily in tests
    arq_pool: providers.Callable[object] = providers.Callable(  # type: ignore[type-arg]
        _create_arq_pool,
        redis_url=settings.provided.redis.url,
    )

    # ──────────────────────────────────────────────
    # Infrastructure — LLM Providers
    # ──────────────────────────────────────────────

    # CRIT-4: RedisCache injected so embed_batch() checks cache before calling OpenAI
    embedding_provider: providers.Singleton[OpenAIEmbeddingService] = providers.Singleton(
        OpenAIEmbeddingService,
        settings=settings.provided.openai,
        cache=redis_cache,
    )

    chat_provider: providers.Singleton[OpenAIChatService] = providers.Singleton(
        OpenAIChatService,
        settings=settings.provided.openai,
    )

    # ──────────────────────────────────────────────
    # Infrastructure — Vector Database
    # ──────────────────────────────────────────────

    vector_repository: providers.Singleton[QdrantVectorRepository] = providers.Singleton(
        QdrantVectorRepository,
        settings=settings.provided.qdrant,
    )

    # ──────────────────────────────────────────────
    # Infrastructure — Chat History
    # ──────────────────────────────────────────────

    chat_history_repository: providers.Singleton[RedisChatHistoryRepository] = providers.Singleton(
        RedisChatHistoryRepository,
        redis_cache=redis_cache,
    )

    # ──────────────────────────────────────────────
    # Application Services (Singletons — stateless)
    # ──────────────────────────────────────────────

    prompt_service: providers.Singleton[PromptService] = providers.Singleton(
        PromptService,
    )

    # IMP-3 + IMP-12: score_threshold and max_context_tokens from settings
    context_service: providers.Singleton[ContextService] = providers.Singleton(
        ContextService,
        token_service=token_service,
        max_context_tokens=settings.provided.rag.max_context_tokens,
        score_threshold=settings.provided.rag.score_threshold,
    )

    # ──────────────────────────────────────────────
    # Use Cases (Factory — new instance per request)
    # ──────────────────────────────────────────────

    # IMP-1: chunk_size and chunk_overlap now come from settings
    process_document: providers.Factory[ProcessDocumentUseCase] = providers.Factory(
        ProcessDocumentUseCase,
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        vector_repository=vector_repository,
        embedding_provider=embedding_provider,
        chunking_strategy=chunking_strategy,
        token_service=token_service,
        chunk_size=settings.provided.chunking.chunk_size,
        chunk_overlap=settings.provided.chunking.chunk_overlap,
    )

    # CRIT-3: Replaced background_worker with arq_pool
    ingest_document: providers.Factory[IngestDocumentUseCase] = providers.Factory(
        IngestDocumentUseCase,
        document_repository=document_repository,
        arq_pool=arq_pool,
    )

    search_documents: providers.Factory[SearchDocumentsUseCase] = providers.Factory(
        SearchDocumentsUseCase,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        token_service=token_service,
    )

    rag_chat: providers.Factory[RAGChatUseCase] = providers.Factory(
        RAGChatUseCase,
        search_use_case=search_documents,
        chat_provider=chat_provider,
        prompt_service=prompt_service,
        context_service=context_service,
        chat_history_repository=chat_history_repository,
        token_service=token_service,
    )


async def _create_arq_pool(redis_url: str) -> object:
    """Resource factory: create an ARQ Redis pool for job enqueueing."""
    from arq import create_pool
    from arq.connections import RedisSettings as ArqRedisSettings

    settings = ArqRedisSettings.from_dsn(redis_url)
    return await create_pool(settings)
