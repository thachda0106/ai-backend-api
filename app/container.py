"""Dependency injection container — the composition root.

This container wires all application layers together using
dependency-injector's DeclarativeContainer. Infrastructure
providers are declared as Dependency stubs that MUST be
provided before the container is used.
"""

from __future__ import annotations

from dependency_injector import containers, providers

from app.core.config.settings import Settings, get_settings
from app.domain.repositories.chat_repository import ChatHistoryRepository
from app.domain.repositories.chunk_repository import ChunkRepository
from app.domain.repositories.document_repository import DocumentRepository
from app.domain.repositories.vector_repository import VectorRepository
from app.domain.services.chunking_service import ChunkingStrategy, SimpleChunkingStrategy
from app.domain.services.token_service import TokenService


class Container(containers.DeclarativeContainer):
    """Application DI container.

    Provides:
    - Configuration and settings
    - Domain services (concrete)
    - Repository stubs (must be overridden with implementations)
    - Infrastructure stubs (must be overridden with implementations)

    Phase 2 will override the Dependency stubs with concrete implementations.
    Phase 3 will add use case Factory providers.
    """

    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.api.routers",
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

    # ──────────────────────────────────────────────
    # Repository Interfaces (stubs — must be provided)
    # These are the dependency inversion points.
    # Phase 2 will override them with concrete implementations.
    # ──────────────────────────────────────────────

    document_repository: providers.Dependency[DocumentRepository] = providers.Dependency(
        instance_of=DocumentRepository,
    )

    chunk_repository: providers.Dependency[ChunkRepository] = providers.Dependency(
        instance_of=ChunkRepository,
    )

    vector_repository: providers.Dependency[VectorRepository] = providers.Dependency(
        instance_of=VectorRepository,
    )

    chat_history_repository: providers.Dependency[ChatHistoryRepository] = providers.Dependency(
        instance_of=ChatHistoryRepository,
    )

    # ──────────────────────────────────────────────
    # Infrastructure Services (stubs — must be provided)
    # ──────────────────────────────────────────────

    token_service: providers.Dependency[TokenService] = providers.Dependency(
        instance_of=TokenService,
    )

    # ──────────────────────────────────────────────
    # Use Cases (Phase 3 — will be added as Factory providers)
    # ──────────────────────────────────────────────
