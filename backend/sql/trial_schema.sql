-- Trial side: subjects, daily diaries, lab results, events, flags, briefs, expedited forms. Idempotent.
CREATE TABLE IF NOT EXISTS trials (
    id       TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    product  TEXT NOT NULL,
    phase    TEXT,
    sites    TEXT[] NOT NULL DEFAULT '{}',
    source   TEXT
);
CREATE TABLE IF NOT EXISTS subjects (
    id        TEXT PRIMARY KEY,
    trial_id  TEXT NOT NULL REFERENCES trials(id),
    site      TEXT NOT NULL,
    age       INT,
    sex       TEXT,
    race      TEXT,
    ref_date  DATE NOT NULL,          -- study day 1
    last_day  INT  NOT NULL
);
-- Patient-reported daily symptoms: one row per subject per day per item. Hypertable: it is the highest-volume stream.
CREATE TABLE IF NOT EXISTS diary_entries (
    subject_id TEXT NOT NULL,
    entry_date DATE NOT NULL,
    study_day  INT  NOT NULL,
    item       TEXT NOT NULL,
    grade      SMALLINT NOT NULL,
    PRIMARY KEY (subject_id, entry_date, item)
);
SELECT create_hypertable('diary_entries', 'entry_date', chunk_time_interval => INTERVAL '30 days', if_not_exists => TRUE);
ALTER TABLE diary_entries SET (timescaledb.compress, timescaledb.compress_segmentby = 'subject_id', timescaledb.compress_orderby = 'entry_date DESC');
SELECT add_compression_policy('diary_entries', INTERVAL '60 days', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS lab_results (
    subject_id  TEXT NOT NULL,
    result_date DATE NOT NULL,
    study_day   INT  NOT NULL,
    test        TEXT NOT NULL,
    value       REAL NOT NULL,
    lln         REAL,
    uln         REAL,
    unit        TEXT,
    visit       TEXT,
    x_uln       REAL,
    PRIMARY KEY (subject_id, result_date, test, visit)
);
SELECT create_hypertable('lab_results', 'result_date', chunk_time_interval => INTERVAL '30 days', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS subject_events (
    subject_id TEXT NOT NULL,
    term       TEXT NOT NULL,
    pt         TEXT,
    soc        TEXT,
    start_day  INT,
    end_day    INT,
    severity   TEXT,
    serious    BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS subject_events_subject ON subject_events (subject_id);

CREATE TABLE IF NOT EXISTS flags (
    id        TEXT PRIMARY KEY,
    trial_id  TEXT NOT NULL,
    subject_id TEXT,
    site      TEXT,
    rule      TEXT NOT NULL,
    severity  TEXT NOT NULL,          -- urgent | review | watch
    fired_on  DATE,
    study_day INT,
    title     TEXT NOT NULL,
    citation  TEXT,
    logic     JSONB NOT NULL,         -- ordered list of sentences: the chain that produced the flag
    evidence  JSONB NOT NULL,
    status    TEXT NOT NULL DEFAULT 'open',   -- open | confirmed | dismissed
    decided_by TEXT,
    decided_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS flags_subject ON flags (subject_id);

CREATE TABLE IF NOT EXISTS briefs (
    id           SERIAL PRIMARY KEY,
    subject_id   TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    body         JSONB NOT NULL,
    assessment   JSONB,
    signed_by    TEXT,
    signed_at    TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS fda_forms (
    id          SERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_type TEXT NOT NULL,        -- intake_case | trial_subject
    source_id   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'draft',   -- draft | verified | submitted
    due_date    DATE,
    clock_days  INT,
    body        JSONB NOT NULL,
    verified_by TEXT,
    verified_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ,
    UNIQUE (source_type, source_id)
);

-- Weekly symptom burden per item across the trial: the signal-watch chart, maintained by policy.
CREATE MATERIALIZED VIEW IF NOT EXISTS diary_weekly
WITH (timescaledb.continuous) AS
SELECT time_bucket('7 days', entry_date) AS week, item,
       avg(grade)::REAL AS mean_grade, count(*) FILTER (WHERE grade >= 3) AS n_severe, count(DISTINCT subject_id) AS n_subjects
FROM diary_entries GROUP BY week, item WITH NO DATA;
SELECT add_continuous_aggregate_policy('diary_weekly', start_offset => INTERVAL '400 days', end_offset => INTERVAL '1 day',
                                       schedule_interval => INTERVAL '1 hour', if_not_exists => TRUE);
