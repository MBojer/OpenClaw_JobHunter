-- migrations/004_commute.sql
-- Adds commute_minutes and commute_mode columns to jobs table.

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS commute_minutes INTEGER;

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS commute_mode VARCHAR(32);

INSERT INTO schema_migrations (version) VALUES ('004_commute')
ON CONFLICT DO NOTHING;
