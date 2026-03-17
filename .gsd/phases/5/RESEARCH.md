---
phase: 5
level: 2
researched_at: 2026-03-17
---

# Phase 5 Research: Docker & Local Development

## Questions Investigated

1. What is the best multi-stage Dockerfile pattern for a Poetry-based FastAPI app?
2. How should the `docker-compose.yml` structure health checks and service startup order?
3. What are the Qdrant Docker image environment variables and volume conventions?
4. Should we use `poetry export → pip install` or `poetry install` in Docker?

---

## Findings

### Topic 1: Multi-Stage Dockerfile — Poetry + FastAPI

**Recommended Pattern: builder → runtime**

Stage 1 (`builder`): Install poetry, export `requirements.txt`, avoid installing dev dependencies.  
Stage 2 (`runtime`): `python:3.13-slim`, copy only the generated `requirements.txt` + app source, run as non-root user.

```dockerfile
# ── Stage 1: builder ──────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir poetry==1.8.*

COPY pyproject.toml poetry.lock ./
RUN poetry export --without-hashes --without dev -o requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies before copying code (layer cache friendly)
COPY --from=builder /build/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user for security
RUN adduser --system --no-create-home appuser
USER appuser

COPY app/ ./app/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Key decisions:**
- `poetry export --without dev` → no poetry at runtime, smaller image
- Layer order: copy lock files FIRST, then code — maximises Docker cache hits
- `python:3.13-slim` preferred over alpine (better C-extension compatibility)
- Non-root user (`appuser`) baked into the image

**Development override:** `docker-compose.yml` mounts source code as a volume with `--reload`, so the `Dockerfile` targets production; dev mode is handled entirely in Compose.

**Recommendation:** Use `poetry export → pip` pattern for production image, `uvicorn --reload` in Compose for development.

---

### Topic 2: docker-compose.yml Structure — Health Checks + Startup Order

**Pattern: `depends_on: condition: service_healthy`**

Each service must define its own `healthcheck`. The `api` and `worker` services use `condition: service_healthy` so they wait for Redis and Qdrant to be ready, eliminating race conditions.

```yaml
services:
  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  qdrant:
    image: qdrant/qdrant:latest
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/readyz"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

  api:
    depends_on:
      redis:
        condition: service_healthy
      qdrant:
        condition: service_healthy

  worker:
    depends_on:
      redis:
        condition: service_healthy
      qdrant:
        condition: service_healthy
```

**Key decisions:**
- Redis health: `redis-cli ping` — reliable, pre-installed in the image
- Qdrant health: `curl -f .../readyz` — official readiness endpoint
- `start_period` accounts for slow cold starts; failures during it don't count
- Worker shares the same image as `api` using a different `command`

---

### Topic 3: Qdrant Docker Image — Configuration + Volumes

**Official image:** `qdrant/qdrant` (latest stable)

**Environment variable naming convention:** `QDRANT__<SECTION>__<KEY>` using double underscores.

Key variables:
| Variable | Purpose |
|---|---|
| `QDRANT__SERVICE__API_KEY` | Enable API key auth |
| `QDRANT__LOG_LEVEL` | Set log verbosity (INFO, DEBUG) |
| `QDRANT__STORAGE__STORAGE_PATH` | Override default `/qdrant/storage` |
| `RUN_MODE` | `production` (default in Docker) or `dev` |

**Volume mount:** Data must be persisted at `/qdrant/storage`. Without a volume mount, data is lost when the container is restarted.

```yaml
qdrant:
  image: qdrant/qdrant:latest
  volumes:
    - qdrant_data:/qdrant/storage
  environment:
    - QDRANT__LOG_LEVEL=INFO
  ports:
    - "6333:6333"  # REST
    - "6334:6334"  # gRPC
```

**Note:** gRPC (port 6334) is disabled by default in the Docker image. Our settings have `PREFER_GRPC=true` — for local dev, force it off or explicitly enable it with `QDRANT__SERVICE__ENABLE_TLS=false` and ensure gRPC port is mapped.

**Recommendation:** For local dev, keep `QDRANT__PREFER_GRPC=false` to avoid additional Qdrant configuration; use gRPC only in cloud deployments where it provides a meaningful performance advantage.

---

### Topic 4: Worker Service in Compose

The background worker (`app.infrastructure.worker`) runs the same Python app with a different entrypoint:

```yaml
worker:
  build:
    context: .
    target: runtime
  command: ["python", "-m", "app.infrastructure.worker.runner"]
  env_file: .env
  depends_on:
    redis:
      condition: service_healthy
    qdrant:
      condition: service_healthy
```

Both `api` and `worker` use the same Docker image (`target: runtime`) via different `command` overrides. In development, source code is mounted as a volume for hot reload.

---

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Poetry installation in Docker | `poetry export → pip install` | No Poetry overhead in runtime image |
| Base image | `python:3.13-slim` | Best balance of size and C-extension compat |
| Health check dependency | `condition: service_healthy` | Eliminates startup race conditions |
| gRPC for local dev | Disabled (`PREFER_GRPC=false`) | Simpler Qdrant local config; enable in prod |
| Source mounting in dev | Volume mount in Compose (not baked in) | No rebuild needed on code change |
| Container user | Non-root `appuser` | Security best practice |

---

## Patterns to Follow

- Two stages in Dockerfile: `builder` (exports requirements) → `runtime` (lean, non-root)
- Copy `pyproject.toml + poetry.lock` before app code to maximize Docker cache hits
- All services define `healthcheck` blocks
- `api` and `worker` use `depends_on: condition: service_healthy` for both Redis and Qdrant
- Use `.env` file via `env_file: .env` in Compose; never bake secrets into images
- Use named volumes (`qdrant_data`, `redis_data`) for data persistence
- Provide a `Makefile` with `make up`, `make down`, `make logs`, `make restart` convenience targets

## Anti-Patterns to Avoid

- **`COPY . .` before installing dependencies**: Breaks Docker layer cache on every code change
- **Running as root**: Security risk in production containers
- **`depends_on` without `condition: service_healthy`**: Only checks container start, not readiness
- **`poetry install` in runtime stage**: Bloats image with Poetry and dev tooling
- **Hardcoded secrets in Dockerfile or Compose**: Use `.env` file + `env_file:` directive
- **No volume for Qdrant storage**: Qdrant data lost on container restart

## Dependencies Identified

No new Python dependencies needed for Phase 5. All infrastructure is configured via:
- `Dockerfile` — multi-stage build file
- `docker-compose.yml` (and `docker-compose.override.yml` for dev)
- `Makefile` — convenience commands
- `.env.example` — already exists, needs a review for completeness

## Risks

- `qdrant/qdrant:latest` tag is mutable — **mitigation:** pin to a specific version tag (e.g., `qdrant/qdrant:v1.14.0`) for reproducibility
- Worker process crashes are not auto-restarted by default — **mitigation:** add `restart: on-failure` to the worker service

## Ready for Planning
- [x] Questions answered
- [x] Approach selected
- [x] Dependencies identified
