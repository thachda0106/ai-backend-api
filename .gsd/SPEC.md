# SPEC.md — Project Specification

> **Status**: `FINALIZED`

## Vision

Build a **production-grade AI Backend API** that powers document ingestion, semantic search, and Retrieval-Augmented Generation (RAG). The system uses FastAPI (Python 3.12+) with Clean Architecture + Domain Driven Design principles, backed by Qdrant for vector storage, Redis for caching/rate-limiting, and OpenAI for embeddings + chat completions. The entire infrastructure is codified in modular Terraform with multi-environment support, making the platform deployable and scalable for real-world production usage.

## Goals

1. **RAG Pipeline** — Implement a complete document ingestion → chunking → embedding → vector storage → retrieval → LLM generation pipeline with streaming responses
2. **Clean Architecture** — Enforce strict separation of concerns across API, Application, Domain, Repository, and Infrastructure layers with dependency inversion
3. **Production Infrastructure** — Provide Docker-based local development and Terraform IaC for AWS deployment with multi-environment support (dev/staging/production)
4. **Observability & Resilience** — Implement structured logging, metrics hooks, tracing readiness, rate limiting, token tracking, retry logic, and error resilience throughout

## Non-Goals (Out of Scope)

- Frontend / UI implementation
- Multi-tenant user management (basic API auth only)
- Fine-tuning or model training
- Supporting multiple vector DB backends (Qdrant only for v1)
- Real-time WebSocket communication (SSE only)
- Full CI/CD pipeline implementation (infrastructure support only)
- Production secrets rotation automation

## Users

- **Backend developers** integrating RAG capabilities into their applications via REST API
- **DevOps engineers** deploying and managing the infrastructure via Terraform
- **AI/ML engineers** extending the pipeline with custom chunking strategies or LLM providers

## Tech Stack

### Backend
- Python 3.12+, FastAPI, Pydantic v2, async-first architecture

### AI / LLM
- OpenAI API (chat completions + embeddings)
- LLM provider abstraction layer for future extensibility

### Vector Database
- Qdrant

### Infrastructure
- Redis (caching + rate limiting)
- Background workers (async document processing)
- Docker + docker-compose (local development)

### Infrastructure as Code
- Terraform (modular, remote state with S3 + DynamoDB locking)
- Multi-environment: dev / staging / production

### Observability
- Structured logging, metrics hooks, tracing-ready architecture

## Constraints

- **Python 3.12+** minimum version
- **OpenAI API** as the initial LLM provider (abstracted for future providers)
- **Qdrant** as the vector database
- **AWS** as the target cloud provider for Terraform infrastructure
- **Environment variables** for all configuration (12-Factor App)
- Must support **streaming responses** via Server-Sent Events (SSE)

## Success Criteria

- [ ] Document ingestion API accepts text documents and triggers background processing pipeline
- [ ] Documents are chunked with configurable size/overlap and stored as vector embeddings in Qdrant
- [ ] Semantic search API returns top-k results with similarity scores and metadata filtering
- [ ] RAG chat API streams LLM responses with context injection and citation references
- [ ] Clean Architecture layers are strictly separated with dependency inversion
- [ ] Docker Compose starts the full local development stack (API, Redis, Qdrant, Worker)
- [ ] Terraform modules deploy the infrastructure to AWS with environment isolation
- [ ] Rate limiting, token tracking, and structured logging are operational
- [ ] All core use cases have corresponding tests
