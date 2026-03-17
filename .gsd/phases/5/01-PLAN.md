---
phase: 5
plan: 1
wave: 1
depends_on: []
files_modified:
  - Dockerfile
autonomous: true

must_haves:
  truths:
    - "Multi-stage Dockerfile exists with builder and runtime stages"
    - "poetry export generates requirements.txt in builder stage"
    - "Runtime image runs as non-root user appuser"
    - "HEALTHCHECK instruction is included"
---

# Plan 5.1: Multi-Stage Dockerfile

## Objective
Create a production-grade multi-stage `Dockerfile` for the FastAPI app using the `poetry export → pip install` pattern. The builder stage extracts pinned dependencies without dev extras; the runtime stage is a slim, non-root image. Development hot-reload is handled entirely in Compose (Plan 5.2), so this file targets production.

## Context
- @pyproject.toml — dependency definitions and Poetry project config
- @app/main.py — uvicorn entry point (`app.main:app`)
- @.gsd/phases/5/RESEARCH.md — Dockerfile pattern decision

## Tasks

<task type="auto">
  <name>Create multi-stage Dockerfile</name>
  <files>
    Dockerfile
  </files>
  <action>
    Create `Dockerfile` at the project root with two named stages:

    **Stage 1: `builder`**
    - Base: `python:3.13-slim`
    - `WORKDIR /build`
    - Install Poetry via pip: `pip install --no-cache-dir "poetry==1.8.*"`
    - Copy ONLY `pyproject.toml` and `poetry.lock` first (cache layer)
    - Run: `poetry export --without-hashes --without dev -o requirements.txt`

    **Stage 2: `runtime`**
    - Base: `python:3.13-slim`
    - Set ENV: `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`
    - `WORKDIR /app`
    - Copy `requirements.txt` from builder: `COPY --from=builder /build/requirements.txt .`
    - Run: `pip install --no-cache-dir -r requirements.txt`
    - Create non-root user: `RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser`
    - Copy app source: `COPY app/ ./app/`
    - Set `USER appuser`
    - `EXPOSE 8000`
    - `HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"`
    - Use `httpx` is already installed; prefer stdlib `urllib.request` in HEALTHCHECK to avoid import overhead.
    - `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]`

    **Anti-patterns to avoid:**
    - Do NOT `COPY . .` before installing requirements — breaks cache
    - Do NOT `RUN pip install poetry` in the runtime stage
    - Do NOT run as root (`USER root` in final stage)
    - Do NOT use `--no-root` with `poetry install` — use `poetry export` instead
  </action>
  <verify>docker build --target runtime -t ai-backend-api:test . && docker inspect ai-backend-api:test --format '{{.Config.User}}'</verify>
  <done>Image builds successfully, reports non-root user (appuser), and HEALTHCHECK is present in inspect output</done>
</task>

## Success Criteria
- [ ] `docker build --target runtime -t ai-backend-api:test .` succeeds with exit code 0
- [ ] `docker inspect ai-backend-api:test --format '{{.Config.User}}'` shows `appuser`
- [ ] `docker inspect ai-backend-api:test --format '{{.Config.Healthcheck}}'` is non-null
