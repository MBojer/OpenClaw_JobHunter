-- migrations/003_notes.sql
-- Adds user_note column to jobs and applications tables.

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS user_note TEXT;

ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS user_note TEXT;

INSERT INTO schema_migrations (version) VALUES ('003_notes')
ON CONFLICT DO NOTHING;
