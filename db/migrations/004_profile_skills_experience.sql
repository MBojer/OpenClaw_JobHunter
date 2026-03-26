-- migrations/004_profile_skills_experience.sql
-- Adds dedicated skills column to profile and creates profile_experience table.
-- Skills: global skill list used by score_jobs.py for matching and agent queries.
-- Experience: one row per role, enabling agent to list/add/remove/edit individual entries.

ALTER TABLE profile
    ADD COLUMN IF NOT EXISTS skills JSONB NOT NULL DEFAULT '{}';

CREATE TABLE IF NOT EXISTS profile_experience (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    company     TEXT NOT NULL,
    from_date   TEXT,        -- YYYY-MM or YYYY
    to_date     TEXT,        -- YYYY-MM, YYYY, or 'present'
    description TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO schema_migrations (version) VALUES ('004_profile_skills_experience')
ON CONFLICT DO NOTHING;
