-- Migration 002 — outbox column + schema_version on the event store.
-- For databases created before this change (01_schema.sql only runs on first
-- container init). Apply with:
--   psql "$CHRONICLE_DB_URL" -f ops/migrations/002_outbox_schema_version.sql

ALTER TABLE events ADD COLUMN IF NOT EXISTS schema_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE events ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;

-- Existing events were already published under the old dual-write path;
-- backfill so the outbox relay doesn't republish history.
UPDATE events SET published_at = NOW() WHERE published_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_events_unpublished ON events(id) WHERE published_at IS NULL;
