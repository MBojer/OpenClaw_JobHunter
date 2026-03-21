-- JobHunter v2 — Full Schema
-- Run via: python scripts/db/migrate.py
-- Or directly: psql $DATABASE_URL -f db/schema.sql

-- ─── Extensions ─────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Boards ──────────────────────────────────────────────────────────────────
-- Registered job board connectors
CREATE TABLE IF NOT EXISTS boards (
    id          SERIAL PRIMARY KEY,
    slug        VARCHAR(64) UNIQUE NOT NULL,   -- e.g. "jobindex", "indeed"
    name        VARCHAR(128) NOT NULL,
    tier        SMALLINT NOT NULL DEFAULT 1,   -- 1=RSS, 2=HTML scraper, 3=manual
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    config      JSONB,                         -- board-specific config (URLs, selectors)
    last_run_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Jobs ────────────────────────────────────────────────────────────────────
-- Every scraped job posting
CREATE TABLE IF NOT EXISTS jobs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    board_id        INTEGER REFERENCES boards(id),
    external_id     VARCHAR(256),              -- board's own ID or URL hash for dedup
    url             TEXT UNIQUE NOT NULL,
    title           VARCHAR(256) NOT NULL,
    company         VARCHAR(256),
    location        VARCHAR(256),
    remote          BOOLEAN,
    salary_raw      VARCHAR(128),              -- as scraped, unparsed
    description_raw TEXT,                      -- NEVER passed to free model
    tags            TEXT[],                    -- extracted by Qwen
    score           SMALLINT,                  -- 0-100, set by score_jobs.py
    score_reason    TEXT,                      -- short explanation from Qwen
    status          VARCHAR(32) NOT NULL DEFAULT 'new',
    -- status: new | reviewed | applied | rejected | hidden | duplicate
    duplicate_of    UUID REFERENCES jobs(id),  -- set when status='duplicate'
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scored_at       TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_score   ON jobs(score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped ON jobs(scraped_at DESC);

-- ─── Run Log ─────────────────────────────────────────────────────────────────
-- Cron execution history — used for monitoring and dedup window
CREATE TABLE IF NOT EXISTS run_log (
    id          SERIAL PRIMARY KEY,
    run_type    VARCHAR(64) NOT NULL,          -- "scrape", "score", "digest"
    board_slug  VARCHAR(64),                   -- null for non-board runs
    status      VARCHAR(32) NOT NULL,          -- "ok" | "error" | "partial"
    jobs_found  INTEGER DEFAULT 0,
    jobs_new    INTEGER DEFAULT 0,
    error_msg   TEXT,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

-- ─── Applications ────────────────────────────────────────────────────────────
-- Tracks document generation and delivery per job
CREATE TABLE IF NOT EXISTS applications (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id          UUID REFERENCES jobs(id),
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    profile_hash    VARCHAR(64),               -- hash of profile at generation time
    input_hash      VARCHAR(64) UNIQUE,        -- SHA256(job_id || profile_hash) — dedup key
    status          VARCHAR(32) NOT NULL DEFAULT 'generated',
    -- status: generated | delivered | failed
    delivered_via   VARCHAR(32),               -- 'telegram' | 'email' | 'both'
    delivered_at    TIMESTAMPTZ,
    notes           TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Documents ────────────────────────────────────────────────────────────────
-- Binary document storage — survives reinstalls, backed up with DB
CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id  UUID REFERENCES applications(id),
    job_id          UUID REFERENCES jobs(id),
    doc_type        VARCHAR(32) NOT NULL,      -- 'cv_docx' | 'cv_pdf' | 'cl_docx' | 'cl_pdf'
    filename        VARCHAR(256) NOT NULL,
    content         BYTEA NOT NULL,            -- full file binary
    content_hash    VARCHAR(64),               -- SHA256 of content for integrity check
    size_bytes      INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Spend Log ───────────────────────────────────────────────────────────────
-- Tracks Together.ai usage to guard the $10 budget
CREATE TABLE IF NOT EXISTS spend_log (
    id              SERIAL PRIMARY KEY,
    provider        VARCHAR(64) NOT NULL DEFAULT 'together',
    model           VARCHAR(128),
    purpose         VARCHAR(64),               -- "cv", "cover_letter"
    job_id          UUID REFERENCES jobs(id),
    prompt_tokens   INTEGER,
    completion_tokens INTEGER,
    estimated_usd   NUMERIC(8,4),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Profile ─────────────────────────────────────────────────────────────────
-- Single-row table — user profile populated by onboarding
-- Stored here for DB-side access by scripts; also mirrored to config/profile.json
CREATE TABLE IF NOT EXISTS profile (
    id              INTEGER PRIMARY KEY DEFAULT 1,  -- always 1
    raw_input       TEXT,                           -- original LinkedIn paste (never shown to free model)
    structured      JSONB NOT NULL DEFAULT '{}',    -- parsed profile
    preferences     JSONB NOT NULL DEFAULT '{}',    -- location, salary, remote preference
    profile_hash    VARCHAR(64),                    -- SHA256 of structured — updated on every save
    onboarded_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT single_row CHECK (id = 1)
);

-- ─── Migrations Tracker ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(64) PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO schema_migrations (version) VALUES ('001_initial')
ON CONFLICT DO NOTHING;
