# ROADMAP.md

> **Current Phase**: Not started
> **Milestone**: v1.0

## Must-Haves (from SPEC)

- [ ] Complete RAG pipeline (ingest → chunk → embed → search → generate)
- [ ] Clean Architecture with strict layer separation
- [ ] Docker local development stack
- [ ] Terraform multi-environment infrastructure
- [ ] Streaming SSE responses
- [ ] Observability and rate limiting

## Phases

### Phase 1: Project Foundation & Domain Layer
**Status**: ⬜ Not Started
**Objective**: Establish the project skeleton with Clean Architecture structure, core configuration, dependency injection, and the domain layer (entities, value objects, repository interfaces, domain services)
**Requirements**: REQ-01, REQ-02

**Key Deliverables:**
- Python project with pyproject.toml, dependencies, linting
- Clean Architecture directory structure (api/, application/, domain/, infrastructure/, repositories/, core/)
- Core config (settings, environment variables, logging setup)
- Domain models: Document, Chunk, Embedding, SearchResult, ChatMessage
- Value objects: DocumentId, ChunkId, EmbeddingVector, etc.
- Repository interfaces (abstract base classes)
- Domain services and business rules

---

### Phase 2: Infrastructure Layer & External Integrations
**Status**: ✅ Complete
**Objective**: Implement all infrastructure adapters — OpenAI client, Qdrant client, Redis cache, background worker system — wired through dependency injection
**Requirements**: REQ-05, REQ-08, REQ-09, REQ-10

**Key Deliverables:**
- OpenAI embedding service (batch processing, retry, rate limit handling)
- OpenAI chat completion service (streaming support)
- LLM provider abstraction interface
- Qdrant vector store adapter
- Redis cache adapter (embedding cache, search result cache)
- Redis-based rate limiter
- Background worker infrastructure (asyncio task queue)
- Repository implementations (in-memory + Qdrant-backed)

---

### Phase 3: Application Layer & Use Cases
**Status**: ✅ Complete
**Objective**: Implement all business workflows — document ingestion, processing pipeline, search, RAG chat — as use cases in the application layer
**Requirements**: REQ-03, REQ-04, REQ-06, REQ-07, REQ-11, REQ-22, REQ-23

**Key Deliverables:**
- Document ingestion use case (upload + trigger background pipeline)
- Document processing pipeline (extract → chunk → embed → store)
- Chunking service (configurable size/overlap)
- Vector search use case (embed query → search Qdrant → rank results)
- RAG chat use case (search → context build → prompt → stream LLM)
- Prompt template service and context window management
- Token counting and usage tracking
- Citation/source reference builder

---

### Phase 4: API Layer & Streaming
**Status**: ⬜ Not Started
**Objective**: Implement FastAPI routers, request/response models, SSE streaming, middleware (rate limiting, auth, logging), and the application entry point
**Requirements**: REQ-03, REQ-06, REQ-07, REQ-12, REQ-13, REQ-22

**Key Deliverables:**
- FastAPI application factory with lifespan management
- POST /documents router (ingestion)
- POST /search router (vector search)
- POST /chat router (RAG with SSE streaming)
- GET /health router
- Pydantic v2 request/response models
- SSE streaming implementation
- Rate limiting middleware
- API key authentication
- Structured logging middleware
- Error handling and response formatting

---

### Phase 5: Docker & Local Development
**Status**: ⬜ Not Started
**Objective**: Containerize the application and provide a complete local development environment
**Requirements**: REQ-14

**Key Deliverables:**
- Multi-stage Dockerfile (development + production)
- docker-compose.yml with services: api, redis, qdrant, worker
- Environment configuration (.env.example)
- Health checks for all services
- Volume mounts for local development
- Startup scripts and Makefile

---

### Phase 6: Terraform Infrastructure
**Status**: ⬜ Not Started
**Objective**: Create modular Terraform IaC for AWS deployment with multi-environment support
**Requirements**: REQ-15, REQ-16, REQ-17, REQ-18, REQ-19, REQ-20, REQ-21

**Key Deliverables:**
- Terraform module: network (VPC, subnets, routing, security groups)
- Terraform module: compute (ECS Fargate, task definitions, auto-scaling)
- Terraform module: redis (ElastiCache Redis cluster)
- Terraform module: qdrant (ECS service for Qdrant)
- Terraform module: registry (ECR repositories)
- Terraform module: observability (CloudWatch, log groups, alarms)
- Environment configs: dev/, staging/, production/
- Remote state: S3 backend + DynamoDB locking
- Variable files and tfvars per environment

---

### Phase 7: Testing & Documentation
**Status**: ⬜ Not Started
**Objective**: Write tests for core use cases, integration tests, and project documentation
**Requirements**: All

**Key Deliverables:**
- Unit tests for domain layer
- Unit tests for application use cases (mocked infrastructure)
- Integration tests for infrastructure adapters
- API endpoint tests
- README.md with setup instructions
- API documentation (example requests/responses)
- Architecture documentation
