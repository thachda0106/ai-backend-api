# DECISIONS.md — Architecture Decision Records

## ADR-001: Clean Architecture + DDD
**Date**: 2026-03-15
**Status**: Accepted
**Context**: Need a scalable, testable backend architecture for an AI platform
**Decision**: Use Clean Architecture with Domain Driven Design, separating into API → Application → Domain → Infrastructure layers with dependency inversion
**Consequences**: More boilerplate code, but excellent testability, maintainability, and provider swappability

## ADR-002: FastAPI with Async-First
**Date**: 2026-03-15
**Status**: Accepted
**Context**: Need a high-performance Python web framework for AI workloads
**Decision**: Use FastAPI with async/await throughout for non-blocking I/O
**Consequences**: Better throughput for I/O-bound LLM/embedding calls, requires async-compatible libraries

## ADR-003: Qdrant for Vector Storage
**Date**: 2026-03-15
**Status**: Accepted
**Context**: Need a vector database for storing and searching document embeddings
**Decision**: Use Qdrant as the vector database
**Consequences**: High-performance similarity search, good Python client, can run locally in Docker

## ADR-004: AWS + Terraform for Infrastructure
**Date**: 2026-03-15
**Status**: Accepted
**Context**: Need cloud infrastructure with IaC for multi-environment deployment
**Decision**: Use AWS with Terraform, ECS Fargate for compute, ElastiCache for Redis, S3+DynamoDB for state
**Consequences**: Production-grade infrastructure, modular and reusable, requires AWS account

## ADR-005: SSE for Streaming Responses
**Date**: 2026-03-15
**Status**: Accepted
**Context**: RAG chat responses should stream tokens as they are generated
**Decision**: Use Server-Sent Events (SSE) for streaming LLM responses
**Consequences**: Simpler than WebSockets for unidirectional streaming, widely supported by clients

## ADR-006: LLM Provider Abstraction
**Date**: 2026-03-15
**Status**: Accepted
**Context**: Starting with OpenAI but need flexibility to switch providers
**Decision**: Create abstract LLM provider interface, implement OpenAI as first concrete provider
**Consequences**: Easy to add Anthropic, local models, etc. without changing business logic

## Phase 1 Decisions

## ADR-007: Poetry for Package Management
**Date**: 2026-03-15
**Status**: Accepted
**Context**: Need a Python package manager for dependency management and project setup
**Decision**: Use Poetry with pyproject.toml for dependency management, virtual environments, and packaging
**Consequences**: Mature ecosystem, lock files for reproducibility, good IDE support

## ADR-008: Ruff for Linting + Formatting
**Date**: 2026-03-15
**Status**: Accepted
**Context**: Need linting and formatting tools for code quality
**Decision**: Use ruff as the all-in-one linter and formatter (replaces flake8, black, isort)
**Consequences**: Fast execution, single tool, consistent configuration in pyproject.toml

## ADR-009: Mypy Strict Mode
**Date**: 2026-03-15
**Status**: Accepted
**Context**: Want strict type safety enforcement across the codebase
**Decision**: Use mypy with strict mode enabled for type checking
**Consequences**: Catches type errors at development time, may require more explicit type annotations

## ADR-010: dependency-injector for DI
**Date**: 2026-03-15
**Status**: Accepted
**Context**: Need a DI container for wiring Clean Architecture layers
**Decision**: Use the `dependency-injector` library for dependency injection
**Consequences**: Full-featured container with factories, singletons, and scoped providers; works well with FastAPI

## ADR-011: pydantic-settings for Configuration
**Date**: 2026-03-15
**Status**: Accepted
**Context**: Need environment-based configuration with validation
**Decision**: Use pydantic-settings for settings management with .env file support
**Consequences**: Type-safe config, automatic env var parsing, validation on startup

## ADR-012: Expanded Domain Model
**Date**: 2026-03-15
**Status**: Accepted
**Context**: Need to decide on domain model granularity for the RAG platform
**Decision**: Include expanded entities: Collection (document grouping), User (token tracking), IngestionJob (pipeline status). Repositories: DocumentRepository, ChunkRepository, VectorRepository, ChatHistoryRepository
**Consequences**: Richer domain model supports multi-collection organization, per-user tracking, and pipeline observability

## ADR-013: Value Objects as Frozen Pydantic Models
**Date**: 2026-03-15
**Status**: Accepted
**Context**: Python lacks native value objects; need immutable domain primitives
**Decision**: Implement value objects as frozen Pydantic BaseModel subclasses (model_config = ConfigDict(frozen=True))
**Consequences**: Immutability enforced by Pydantic, validation built-in, hashable for use as dict keys
