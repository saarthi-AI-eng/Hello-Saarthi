-- Add profile columns to saarthi_users (for DBs created before these existed).
-- Idempotent: safe to run multiple times.
ALTER TABLE saarthi_users ADD COLUMN IF NOT EXISTS bio TEXT;
ALTER TABLE saarthi_users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512);
