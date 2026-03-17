-- =========================================================
-- AI Backend API — Database Migration
-- Run once against a fresh PostgreSQL database.
-- Compatible with PostgreSQL 14+
-- =========================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Tenants ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    api_key_hash    VARCHAR(64)  NOT NULL UNIQUE,   -- SHA-256 hex
    plan            VARCHAR(50)  NOT NULL DEFAULT 'free',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    tokens_used_this_month  BIGINT NOT NULL DEFAULT 0,
    total_tokens_used       BIGINT NOT NULL DEFAULT 0,
    metadata        JSONB        NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenants_api_key_hash ON tenants(api_key_hash);
CREATE INDEX IF NOT EXISTS idx_tenants_tenant_id    ON tenants(tenant_id);

-- ── Documents ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID        NOT NULL UNIQUE,
    tenant_id       UUID        NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    collection_id   UUID        NOT NULL,
    title           VARCHAR(1024) NOT NULL,
    content         TEXT        NOT NULL,
    content_type    VARCHAR(100) NOT NULL DEFAULT 'text/plain',
    content_hash    VARCHAR(64),                        -- SHA-256 for dedup
    status          VARCHAR(50)  NOT NULL DEFAULT 'pending',
    chunk_count     INTEGER      NOT NULL DEFAULT 0,
    token_count     INTEGER      NOT NULL DEFAULT 0,
    error_message   TEXT,
    metadata        JSONB        NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_document_id   ON documents(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_tenant_id     ON documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_collection_id ON documents(tenant_id, collection_id);
CREATE INDEX IF NOT EXISTS idx_documents_status        ON documents(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash  ON documents(tenant_id, content_hash)
    WHERE content_hash IS NOT NULL;

-- ── Ingestion Jobs ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          UUID        NOT NULL UNIQUE,
    tenant_id       UUID        NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    document_id     UUID        NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    status          VARCHAR(50)  NOT NULL DEFAULT 'queued',
    total_chunks    INTEGER      NOT NULL DEFAULT 0,
    processed_chunks INTEGER     NOT NULL DEFAULT 0,
    error_message   TEXT,
    arq_job_id      VARCHAR(255),                       -- ARQ job reference
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_job_id      ON ingestion_jobs(job_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_tenant_id   ON ingestion_jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_document_id ON ingestion_jobs(document_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status      ON ingestion_jobs(tenant_id, status);

-- ── Auto-update triggers for updated_at ───────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER trg_ingestion_jobs_updated_at
    BEFORE UPDATE ON ingestion_jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
