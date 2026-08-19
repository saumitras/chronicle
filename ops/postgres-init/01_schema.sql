-- Chronicle — PostgreSQL Schema
-- Runs automatically via docker-entrypoint-initdb.d on first container start.

\c chronicle

-- ── Event Store (append-only) ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id               BIGSERIAL PRIMARY KEY,
    event_id         UUID        NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    aggregate_id     UUID        NOT NULL,
    stream_version   INTEGER     NOT NULL,
    event_type       VARCHAR(100) NOT NULL,
    timestamp        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    producer         VARCHAR(100) NOT NULL,
    correlation_id   UUID,
    causation_id     UUID,
    workflow_id      VARCHAR(255),
    trace_id         VARCHAR(255),
    schema_version   INTEGER     NOT NULL DEFAULT 1,
    payload          JSONB       NOT NULL DEFAULT '{}',
    -- Outbox: NULL until the relay has published this event to Kafka
    published_at     TIMESTAMPTZ,
    UNIQUE (aggregate_id, stream_version)
);

-- ── Read Models ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investigations (
    investigation_id UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id         UUID        NOT NULL,
    workflow_id      VARCHAR(255),
    status           VARCHAR(50) NOT NULL DEFAULT 'running',
    decision         VARCHAR(20),
    risk_score       FLOAT,
    reviewer_id      VARCHAR(255),
    reviewer_comment TEXT,
    payload          JSONB       NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id  UUID        NOT NULL,
    account_id   UUID,
    device_id    UUID,
    merchant     VARCHAR(255),
    amount       NUMERIC(12,2),
    currency     VARCHAR(10) NOT NULL DEFAULT 'USD',
    country      VARCHAR(100),
    vpn_detected BOOLEAN     NOT NULL DEFAULT FALSE,
    status       VARCHAR(50) NOT NULL DEFAULT 'pending',
    payload      JSONB       NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Seed reference tables ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS seed_customers (
    customer_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              VARCHAR(255) NOT NULL,
    email             VARCHAR(255),
    account_age_days  INTEGER NOT NULL DEFAULT 0,
    transaction_avg   NUMERIC(10,2) NOT NULL DEFAULT 0,
    prior_alerts      INTEGER NOT NULL DEFAULT 0,
    risk_profile      VARCHAR(20) NOT NULL DEFAULT 'low'
);

CREATE TABLE IF NOT EXISTS seed_devices (
    device_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id  UUID NOT NULL,
    device_type  VARCHAR(50),
    first_seen   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    known        BOOLEAN NOT NULL DEFAULT TRUE,
    fraud_flags  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS seed_merchants (
    merchant_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(255) NOT NULL,
    category     VARCHAR(100),
    country      VARCHAR(100),
    risk_level   VARCHAR(20) NOT NULL DEFAULT 'low'
);

CREATE TABLE IF NOT EXISTS seed_countries (
    country_code VARCHAR(10) PRIMARY KEY,
    country_name VARCHAR(100) NOT NULL,
    risk_level   VARCHAR(20) NOT NULL DEFAULT 'low'
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_events_aggregate    ON events(aggregate_id, stream_version);
CREATE INDEX IF NOT EXISTS idx_events_type         ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp    ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_correlation  ON events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_events_unpublished  ON events(id) WHERE published_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_investigations_status ON investigations(status);
CREATE INDEX IF NOT EXISTS idx_investigations_alert  ON investigations(alert_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status       ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_customer     ON alerts(customer_id);

-- ── Grants ────────────────────────────────────────────────────────────────────
GRANT ALL ON ALL TABLES IN SCHEMA public TO chronicle;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO chronicle;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO chronicle;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO chronicle;
