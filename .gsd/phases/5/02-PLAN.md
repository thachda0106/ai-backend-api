---
phase: 5
plan: 2
wave: 1
depends_on: []
files_modified:
  - docker-compose.yml
  - .env.example
autonomous: true

must_haves:
  truths:
    - "docker-compose.yml defines 4 services: redis, qdrant, api, worker"
    - "redis and qdrant have healthcheck blocks"
    - "api and worker use depends_on: condition: service_healthy"
    - "Named volumes are declared for qdrant_data and redis_data"
    - ".env.example is complete with all required variables"
---

# Plan 5.2: docker-compose.yml & Environment Configuration

## Objective
Create `docker-compose.yml` defining the complete local development stack: Redis, Qdrant, API, and Worker. All services have health checks; API and Worker wait for dependencies to be healthy before starting. A separate `docker-compose.override.yml` activates hot-reload for development. Also, audit and complete `.env.example`.

## Context
- @Dockerfile — built in Plan 5.1 (target: runtime)
- @.env.example — existing environment template to be completed
- @app/infrastructure/queue/worker.py — worker entry point
- @app/core/config/settings.py — all settings keys needed in .env
- @.gsd/phases/5/RESEARCH.md — Compose patterns and Qdrant env vars

## Tasks

<task type="auto">
  <name>Create docker-compose.yml with health checks and startup ordering</name>
  <files>
    docker-compose.yml
    docker-compose.override.yml
  </files>
  <action>
    Create `docker-compose.yml` at the project root:

    ```yaml
    services:
      redis:
        image: redis:7-alpine
        restart: unless-stopped
        ports:
          - "6379:6379"
        volumes:
          - redis_data:/data
        healthcheck:
          test: ["CMD", "redis-cli", "ping"]
          interval: 10s
          timeout: 5s
          retries: 5
          start_period: 10s

      qdrant:
        image: qdrant/qdrant:v1.14.0    # pinned version, not :latest
        restart: unless-stopped
        ports:
          - "6333:6333"
          - "6334:6334"
        volumes:
          - qdrant_data:/qdrant/storage
        environment:
          - QDRANT__LOG_LEVEL=INFO
          - QDRANT__SERVICE__GRPC_PORT=6334
        healthcheck:
          test: ["CMD-SHELL", "curl -sf http://localhost:6333/readyz || exit 1"]
          interval: 10s
          timeout: 5s
          retries: 5
          start_period: 20s

      api:
        build:
          context: .
          target: runtime
        restart: unless-stopped
        ports:
          - "8000:8000"
        env_file: .env
        environment:
          - REDIS__URL=redis://redis:6379/0
          - QDRANT__URL=http://qdrant:6333
          - QDRANT__PREFER_GRPC=false
        depends_on:
          redis:
            condition: service_healthy
          qdrant:
            condition: service_healthy
        healthcheck:
          test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\""]
          interval: 30s
          timeout: 10s
          retries: 3
          start_period: 20s

      worker:
        build:
          context: .
          target: runtime
        command: ["python", "-m", "app.infrastructure.queue.worker"]
        restart: on-failure
        env_file: .env
        environment:
          - REDIS__URL=redis://redis:6379/0
          - QDRANT__URL=http://qdrant:6333
          - QDRANT__PREFER_GRPC=false
        depends_on:
          redis:
            condition: service_healthy
          qdrant:
            condition: service_healthy

    volumes:
      redis_data:
      qdrant_data:
    ```

    Create `docker-compose.override.yml` for development hot-reload:

    ```yaml
    # Development overrides — applied automatically when running `docker compose up`
    services:
      api:
        build:
          target: runtime
        command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
        volumes:
          - ./app:/app/app   # Mount source for hot reload
        environment:
          - DEBUG=true
          - LOG_LEVEL=DEBUG

      worker:
        volumes:
          - ./app:/app/app   # Mount source for hot reload
        environment:
          - LOG_LEVEL=DEBUG
    ```

    **Key notes:**
    - Use `environment:` for service-to-service URLs (`REDIS__URL`, `QDRANT__URL`) — these override anything in `.env` and ensure containers use internal Docker network names, not `localhost`
    - Pin Qdrant to `v1.14.0` (not `:latest`) for reproducibility
    - `restart: on-failure` on worker handles crash loops without infinite restart
    - Override file is automatically applied by `docker compose up` — no `--file` flag needed
  </action>
  <verify>docker compose config --quiet && echo "Compose config valid"</verify>
  <done>docker compose config exits 0 with no errors; all 4 services visible in output</done>
</task>

<task type="auto">
  <name>Audit and complete .env.example</name>
  <files>
    .env.example
  </files>
  <action>
    Review the existing `.env.example` and add any missing variables. The complete file should include:

    ```
    # Application
    APP_NAME=AI Backend API
    DEBUG=false
    LOG_LEVEL=INFO

    # API Authentication
    API_KEY=change-me-in-production

    # OpenAI
    OPENAI__API_KEY=sk-your-openai-key-here
    OPENAI__MODEL=gpt-4o
    OPENAI__EMBEDDING_MODEL=text-embedding-3-small
    OPENAI__MAX_RETRIES=3
    OPENAI__EMBEDDING_DIMENSIONS=1536
    OPENAI__TEMPERATURE=0.7
    OPENAI__MAX_TOKENS=2048

    # Redis
    REDIS__URL=redis://localhost:6379/0

    # Qdrant
    QDRANT__URL=http://localhost:6333
    QDRANT__COLLECTION_NAME=documents
    QDRANT__PREFER_GRPC=false

    # Chunking
    CHUNKING__CHUNK_SIZE=512
    CHUNKING__CHUNK_OVERLAP=50

    # Rate Limiting
    RATE_LIMIT__REQUESTS_PER_MINUTE=60
    RATE_LIMIT__BURST_SIZE=10
    ```

    Replace the current file completely with the above. Use `REDIS__URL` instead of `REDIS__HOST` + `REDIS__PORT` to match the application's `settings.py` `redis.url` field. If settings.py uses host+port rather than url, use whichever keys match the actual Settings class.

    **Important:** Check `app/core/config/settings.py` before writing to ensure the variable names match the Pydantic settings nested field names exactly using `__` as separator.
  </action>
  <verify>poetry run python -c "from app.core.config.settings import Settings; print('Settings OK')"</verify>
  <done>.env.example contains all settings keys; Settings class loads without errors when env vars from .env.example are present</done>
</task>

## Success Criteria
- [ ] `docker compose config` exits 0 with no validation errors
- [ ] All 4 services (redis, qdrant, api, worker) visible in compose output
- [ ] `depends_on` with `condition: service_healthy` present for api and worker
- [ ] Named volumes `redis_data` and `qdrant_data` declared
- [ ] `docker-compose.override.yml` mounts `./app` for dev hot-reload
- [ ] `.env.example` keys match `settings.py` field names
