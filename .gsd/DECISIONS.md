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
