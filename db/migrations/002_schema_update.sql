-- migrations/002_schema_update.sql
-- Handles existing installs that ran the original schema.
-- Adds: duplicate_of to jobs, profile_hash to profile,
--       replaces applications table, adds documents table.

-- ─── jobs ────────────────────────────────────────────────────────────────────
ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS duplicate_of UUID REFERENCES jobs(id);

-- Add 'duplicate' as a valid status (no constraint to alter, just documentation)
-- Update any code using the old status values is handled in application logic.

-- ─── profile ─────────────────────────────────────────────────────────────────
ALTER TABLE profile
    ADD COLUMN IF NOT EXISTS profile_hash VARCHAR(64);

-- ─── applications — rebuild ───────────────────────────────────────────────────
-- Drop old outbound-email-centric columns if they exist
ALTER TABLE applications
    DROP COLUMN IF EXISTS applied_at,
    DROP COLUMN IF EXISTS cv_path,
    DROP COLUMN IF EXISTS cover_path,
    DROP COLUMN IF EXISTS email_to,
    DROP COLUMN IF EXISTS email_subject,
    DROP COLUMN IF EXISTS email_message_id;

-- Add new delivery-centric columns
ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS generated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS profile_hash   VARCHAR(64),
    ADD COLUMN IF NOT EXISTS input_hash     VARCHAR(64),
    ADD COLUMN IF NOT EXISTS delivered_via  VARCHAR(32),
    ADD COLUMN IF NOT EXISTS delivered_at   TIMESTAMPTZ;

-- Add unique constraint on input_hash if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'applications_input_hash_key'
    ) THEN
        ALTER TABLE applications ADD CONSTRAINT applications_input_hash_key UNIQUE (input_hash);
    END IF;
END $$;

-- Update status default
ALTER TABLE applications ALTER COLUMN status SET DEFAULT 'generated';

-- ─── documents — new table ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id  UUID REFERENCES applications(id),
    job_id          UUID REFERENCES jobs(id),
    doc_type        VARCHAR(32) NOT NULL,
    filename        VARCHAR(256) NOT NULL,
    content         BYTEA NOT NULL,
    content_hash    VARCHAR(64),
    size_bytes      INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO schema_migrations (version) VALUES ('002_schema_update')
ON CONFLICT DO NOTHING;
