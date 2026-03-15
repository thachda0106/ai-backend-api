"""Dependency injection container — the composition root.

This container wires all application layers together using
dependency-injector's DeclarativeContainer. All infrastructure
providers are concrete Singleton/Factory instances.
"""

from __future__ import annotations

from dependency_injector import containers, providers

from app.core.config.settings import Settings, get_settings
from app.domain.services.chunking_service import ChunkingStrategy, SimpleChunkingStrategy

# Infrastructure imports
from app.infrastructure.cache.rate_limiter import RedisRateLimiter
from app.infrastructure.cache.redis_cache import RedisCache
from app.infrastructure.llm.openai_chat import OpenAIChatService
from app.infrastructure.llm.openai_embedding import OpenAIEmbeddingService
from app.infrastructure.queue.worker import BackgroundWorker
from app.infrastructure.repositories.memory_chunk_repo import InMemoryChunkRepository
from app.infrastructure.repositories.memory_document_repo import InMemoryDocumentRepository
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


class Container(containers.DeclarativeContainer):
    """Application DI container.

    Provides:
    - Configuration and settings
    - Domain services (concrete Singletons)
    - Infrastructure adapters (concrete Singletons)
    - Application services (Singletons)
    - Use cases (Factory — new instance per request)
    """

    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.api.routers",
            "app.main",
        ],
    )

    # ──────────────────────────────────────────────
    # Configuration
    # ──────────────────────────────────────────────

    settings: providers.Singleton[Settings] = providers.Singleton(get_settings)

    # ──────────────────────────────────────────────
    # Domain Services
    # ──────────────────────────────────────────────

    chunking_strategy: providers.Singleton[ChunkingStrategy] = providers.Singleton(
        SimpleChunkingStrategy,
    )

    token_service: providers.Singleton[TiktokenService] = providers.Singleton(
        TiktokenService,
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

    # ──────────────────────────────────────────────
    # Infrastructure — LLM Providers
    # ──────────────────────────────────────────────

    embedding_provider: providers.Singleton[OpenAIEmbeddingService] = providers.Singleton(
        OpenAIEmbeddingService,
        settings=settings.provided.openai,
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
    # Infrastructure — Repositories
    # ──────────────────────────────────────────────

    document_repository: providers.Singleton[InMemoryDocumentRepository] = providers.Singleton(
        InMemoryDocumentRepository,
    )

    chunk_repository: providers.Singleton[InMemoryChunkRepository] = providers.Singleton(
        InMemoryChunkRepository,
    )

    chat_history_repository: providers.Singleton[RedisChatHistoryRepository] = providers.Singleton(
        RedisChatHistoryRepository,
        redis_cache=redis_cache,
    )

    # ──────────────────────────────────────────────
    # Infrastructure — Background Worker
    # ──────────────────────────────────────────────

    background_worker: providers.Singleton[BackgroundWorker] = providers.Singleton(
        BackgroundWorker,
        max_concurrent=5,
    )

    # ──────────────────────────────────────────────
    # Application Services (Singletons — stateless)
    # ──────────────────────────────────────────────

    prompt_service: providers.Singleton[PromptService] = providers.Singleton(
        PromptService,
    )

    context_service: providers.Singleton[ContextService] = providers.Singleton(
        ContextService,
        token_service=token_service,
        max_context_tokens=3000,
    )

    # ──────────────────────────────────────────────
    # Use Cases (Factory — new instance per request)
    # ──────────────────────────────────────────────

    process_document: providers.Factory[ProcessDocumentUseCase] = providers.Factory(
        ProcessDocumentUseCase,
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        vector_repository=vector_repository,
        embedding_provider=embedding_provider,
        chunking_strategy=chunking_strategy,
        token_service=token_service,
    )

    ingest_document: providers.Factory[IngestDocumentUseCase] = providers.Factory(
        IngestDocumentUseCase,
        document_repository=document_repository,
        background_worker=background_worker,
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

