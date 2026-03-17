# ── Stage 1: builder ──────────────────────────────────────────
# Installs Poetry, exports pinned requirements.txt without dev deps.
# Poetry is NOT included in the final image.
FROM python:3.13-slim AS builder

WORKDIR /build

# Install Poetry (pinned version for reproducibility)
RUN pip install --no-cache-dir "poetry==1.8.*"

# Copy lock files FIRST to maximise Docker layer cache hits.
# Dependency layer only rebuilds when pyproject.toml or poetry.lock changes.
COPY pyproject.toml poetry.lock ./

# Export pinned runtime deps to requirements.txt (no hashes, no dev extras)
RUN poetry export --without-hashes --without dev -o requirements.txt


# ── Stage 2: runtime ──────────────────────────────────────────
# Lean production image — no Poetry, no dev tools, non-root user.
FROM python:3.13-slim AS runtime

# Prevent Python from writing .pyc files and ensure stdout/stderr are unbuffered
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install curl for health check (minimal addition)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from builder stage and install — before copying app code
COPY --from=builder /build/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root system user for security
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --no-create-home appuser

# Copy application source (code change only invalidates this layer)
COPY app/ ./app/

# Switch to non-root user
USER appuser

EXPOSE 8000

# Health check using stdlib urllib (no extra deps, avoids httpx startup overhead)
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Production server — single worker (scale via container replicas, not threads)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
