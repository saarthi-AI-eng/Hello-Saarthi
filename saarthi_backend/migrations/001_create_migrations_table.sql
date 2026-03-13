-- Migration tracking table. Run first.
-- Idempotent: safe to run multiple times.
CREATE TABLE IF NOT EXISTS saarthi_schema_version (
    version VARCHAR(32) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
