-- Sourced ledger on Tiger Data (TimescaleDB + pgvector). Idempotent.
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS patients (
    id           TEXT PRIMARY KEY,
    display_name TEXT,
    birth_date   DATE,
    sex          TEXT,
    race         TEXT,
    kind         TEXT NOT NULL DEFAULT 'adult',   -- adult (trial subject) | child
    trial_id     TEXT,
    site         TEXT,
    ref_date     DATE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS patient_identifiers (
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    org        TEXT NOT NULL,
    local_id   TEXT NOT NULL,
    PRIMARY KEY (org, local_id)
);
-- Raw documents, kept unchanged. The hash is the proof the text is what arrived.
CREATE TABLE IF NOT EXISTS documents (
    id            TEXT PRIMARY KEY,
    patient_id    TEXT REFERENCES patients(id) ON DELETE CASCADE,
    source_org    TEXT NOT NULL,
    kind          TEXT NOT NULL,
    received_at   TIMESTAMPTZ NOT NULL,
    document_date DATE,
    sha256        TEXT NOT NULL,
    text          TEXT NOT NULL,
    n_pages       INT NOT NULL DEFAULT 1,
    status        TEXT NOT NULL DEFAULT 'pending',   -- pending | read | failed
    reader        TEXT,
    n_facts       INT,
    read_at       TIMESTAMPTZ
);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS image BYTEA;        -- the photo, scan, or PDF as received
ALTER TABLE documents ADD COLUMN IF NOT EXISTS image_type TEXT;
-- Vector index over document text, for "where in this patient's records is X".
CREATE TABLE IF NOT EXISTS document_chunks (
    id          SERIAL PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    patient_id  TEXT,
    page        INT NOT NULL,
    chunk_index INT NOT NULL,
    text        TEXT NOT NULL,
    embedding   vector(384) NOT NULL
);
CREATE INDEX IF NOT EXISTS document_chunks_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops);
-- The ledger. One row per fact, with its receipt. Time-partitioned on when the fact was true.
CREATE TABLE IF NOT EXISTS facts (
    id           BIGSERIAL,
    patient_id   TEXT NOT NULL,
    concept      TEXT NOT NULL,
    display      TEXT NOT NULL,
    value_num    DOUBLE PRECISION,
    value_text   TEXT,
    unit         TEXT,
    observed_at  TIMESTAMPTZ NOT NULL,
    end_at       TIMESTAMPTZ,
    attrs        JSONB NOT NULL DEFAULT '{}',
    source_org   TEXT NOT NULL,
    document_id  TEXT,
    page         INT,
    span_start   INT,
    span_end     INT,
    quote        TEXT,
    resource_ref TEXT,
    extractor    TEXT NOT NULL,
    confidence   REAL NOT NULL,
    status       TEXT NOT NULL DEFAULT 'extracted',   -- extracted | verified | rejected
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, observed_at)
);
SELECT create_hypertable('facts', 'observed_at', chunk_time_interval => INTERVAL '180 days', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS facts_patient_concept ON facts (patient_id, concept, observed_at DESC);
CREATE INDEX IF NOT EXISTS facts_document ON facts (document_id);
ALTER TABLE facts SET (timescaledb.compress, timescaledb.compress_segmentby = 'patient_id', timescaledb.compress_orderby = 'observed_at DESC');
SELECT add_compression_policy('facts', INTERVAL '400 days', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS form_definitions (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    domain      TEXT NOT NULL,
    description TEXT,
    fields      JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS form_instances (
    id         SERIAL PRIMARY KEY,
    form_id    TEXT NOT NULL REFERENCES form_definitions(id),
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    visit_date DATE NOT NULL,
    status     TEXT NOT NULL DEFAULT 'draft',   -- draft | in_review | signed
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    filled_ms  INT,
    n_fields   INT NOT NULL DEFAULT 0,
    n_filled   INT NOT NULL DEFAULT 0,
    n_flagged  INT NOT NULL DEFAULT 0,
    signed_by  TEXT,
    signed_at  TIMESTAMPTZ,
    export     JSONB
);
CREATE INDEX IF NOT EXISTS form_instances_patient ON form_instances (patient_id, visit_date);
CREATE TABLE IF NOT EXISTS form_fields (
    instance_id  INT NOT NULL REFERENCES form_instances(id) ON DELETE CASCADE,
    key          TEXT NOT NULL,
    label        TEXT NOT NULL,
    vtype        TEXT NOT NULL,
    unit         TEXT,
    value        JSONB,
    fact_id      BIGINT,
    confidence   REAL,
    receipt      JSONB,
    alternatives JSONB,
    rows         JSONB,
    verifier     JSONB,
    decision     JSONB,
    PRIMARY KEY (instance_id, key)
);
-- Append-only audit trail.
CREATE TABLE IF NOT EXISTS audit_log (
    at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor     TEXT NOT NULL,
    action    TEXT NOT NULL,
    entity    TEXT,
    entity_id TEXT,
    field     TEXT,
    old_value JSONB,
    new_value JSONB,
    reason    TEXT
);
SELECT create_hypertable('audit_log', 'at', if_not_exists => TRUE);
-- Tamper evidence: every event carries the SHA-256 of the previous event's hash plus its own canonical content.
CREATE SEQUENCE IF NOT EXISTS audit_seq;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS seq BIGINT DEFAULT nextval('audit_seq');
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS prev_hash TEXT;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS hash TEXT;
CREATE INDEX IF NOT EXISTS audit_entity ON audit_log (entity, entity_id, at DESC);
-- Facts arriving per day per source: the "data left behind" chart.
CREATE MATERIALIZED VIEW IF NOT EXISTS facts_daily
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', observed_at) AS day, source_org, count(*) AS n
FROM facts GROUP BY day, source_org WITH NO DATA;
SELECT add_continuous_aggregate_policy('facts_daily', start_offset => INTERVAL '3 years', end_offset => INTERVAL '1 hour', schedule_interval => INTERVAL '1 hour', if_not_exists => TRUE);
