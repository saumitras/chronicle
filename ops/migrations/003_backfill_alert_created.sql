-- Migration 003 — backfill AlertCreated events for alerts that predate
-- store-first alert creation.
--
-- Before this release, live AlertCreated events were published to Kafka only
-- and never written to the event store, so a projection replay would drop
-- those alerts from the read model. This synthesizes the missing facts at
-- stream_version 0 from the current alerts read-model rows.
-- published_at is set so the outbox relay does not republish them (the read
-- models already reflect these alerts).
--
-- Apply AFTER 002:
--   psql "$CHRONICLE_DB_URL" -f ops/migrations/003_backfill_alert_created.sql

INSERT INTO events
  (event_id, aggregate_id, stream_version, event_type, timestamp,
   producer, correlation_id, causation_id, workflow_id, trace_id,
   schema_version, payload, published_at)
SELECT
  gen_random_uuid(),
  a.alert_id,
  0,
  'AlertCreated',
  a.created_at,
  'alert-generator',
  a.alert_id,
  NULL, NULL, NULL,
  1,
  a.payload,
  NOW()
FROM alerts a
WHERE NOT EXISTS (
  SELECT 1 FROM events e
  WHERE e.aggregate_id = a.alert_id AND e.event_type = 'AlertCreated'
)
ON CONFLICT (aggregate_id, stream_version) DO NOTHING;
