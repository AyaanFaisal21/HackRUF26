-- Day Zero schema for Tiger Data (TimescaleDB + pgvector). Idempotent.
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;

-- Intake stream: every raw report, partitioned by time. Hypertable so volume spikes, aging and compression are native.
CREATE TABLE IF NOT EXISTS messages (
    id            TEXT        NOT NULL,
    received_at   TIMESTAMPTZ NOT NULL,
    channel       TEXT        NOT NULL,
    language      TEXT,
    sender        TEXT,
    subject       TEXT,
    body          TEXT        NOT NULL,
    extraction    JSONB,
    case_id       TEXT,
    PRIMARY KEY (id, received_at)
);
SELECT create_hypertable('messages', 'received_at', if_not_exists => TRUE);
ALTER TABLE messages SET (timescaledb.compress, timescaledb.compress_segmentby = 'channel', timescaledb.compress_orderby = 'received_at DESC');
SELECT add_compression_policy('messages', INTERVAL '7 days', if_not_exists => TRUE);

-- Semantic index for duplicate detection (pgvector). Dimension matches dayzero.embed.DIM.
CREATE TABLE IF NOT EXISTS message_embeddings (
    message_id TEXT PRIMARY KEY,
    embedding  vector(384) NOT NULL
);
CREATE INDEX IF NOT EXISTS message_embeddings_hnsw ON message_embeddings USING hnsw (embedding vector_cosine_ops);

-- Relational core: one row per case, child rows for products and reactions.
CREATE TABLE IF NOT EXISTS cases (
    id                   TEXT PRIMARY KEY,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    status               TEXT NOT NULL DEFAULT 'new',
    merged_into          TEXT,
    patient_identifiable BOOLEAN NOT NULL,
    patient_initials     TEXT,
    patient_age          INT,
    patient_sex          TEXT,
    reporter_identifiable BOOLEAN NOT NULL,
    reporter_name        TEXT,
    reporter_qualification TEXT,
    event_date           DATE,
    valid                BOOLEAN NOT NULL,
    missing              TEXT[]  NOT NULL DEFAULT '{}',
    serious              BOOLEAN NOT NULL,
    criteria             TEXT[]  NOT NULL DEFAULT '{}',
    expectedness         TEXT    NOT NULL,
    expedited            BOOLEAN NOT NULL,
    day_zero             DATE,
    due_date             DATE,
    clock_days           INT,
    record               JSONB   NOT NULL,          -- full CaseRecord for the API
    embedding            vector(384)
);
CREATE TABLE IF NOT EXISTS case_drugs (
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    name    TEXT NOT NULL,
    role    TEXT NOT NULL,
    dose    TEXT,
    start_date TEXT
);
CREATE TABLE IF NOT EXISTS case_reactions (
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    term    TEXT NOT NULL,
    pt      TEXT,
    outcome TEXT,
    onset_date TEXT
);
CREATE TABLE IF NOT EXISTS case_duplicates (
    case_id       TEXT NOT NULL,
    other_case_id TEXT NOT NULL,
    score         REAL NOT NULL,
    structured    REAL NOT NULL,
    semantic      REAL NOT NULL,
    evidence      JSONB NOT NULL,
    verdict       TEXT NOT NULL,
    decided       TEXT,                 -- null until a human says merge / not_duplicate
    PRIMARY KEY (case_id, other_case_id)
);

-- Audit trail: append-only, time-partitioned. Every creation, merge, edit and confirmation lands here.
CREATE TABLE IF NOT EXISTS case_audit (
    case_id    TEXT        NOT NULL,
    at         TIMESTAMPTZ NOT NULL,
    actor      TEXT        NOT NULL,
    action     TEXT        NOT NULL,
    field      TEXT,
    old_value  JSONB,
    new_value  JSONB,
    message_id TEXT,
    reason     TEXT
);
SELECT create_hypertable('case_audit', 'at', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS case_audit_case ON case_audit (case_id, at DESC);

-- Continuous aggregate: intake volume per hour per channel, kept fresh by policy, read by the dashboard chart.
CREATE MATERIALIZED VIEW IF NOT EXISTS intake_hourly
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', received_at) AS bucket, channel, count(*) AS n
FROM messages
GROUP BY bucket, channel
WITH NO DATA;
SELECT add_continuous_aggregate_policy('intake_hourly', start_offset => INTERVAL '90 days', end_offset => INTERVAL '1 minute',
                                       schedule_interval => INTERVAL '15 minutes', if_not_exists => TRUE);

-- Work queue: open cases ordered by deadline, with live time remaining.
CREATE OR REPLACE VIEW queue AS
SELECT id, status, valid, missing, serious, criteria, expectedness, expedited, day_zero, due_date, clock_days,
       patient_initials, patient_age, patient_sex, reporter_qualification,
       CASE WHEN due_date IS NULL THEN NULL ELSE (due_date - CURRENT_DATE) END AS days_left,
       (SELECT count(*) FROM case_duplicates d WHERE d.case_id = c.id AND d.decided IS NULL) AS open_duplicates,
       (SELECT count(*) FROM messages m WHERE m.case_id = c.id) AS n_messages
FROM cases c
WHERE merged_into IS NULL AND status <> 'closed'
ORDER BY (due_date IS NULL), due_date, serious DESC;
