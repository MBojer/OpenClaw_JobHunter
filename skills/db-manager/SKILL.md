# Skill: DB Manager

## Purpose
Defines how the agent queries the PostgreSQL database.
The agent uses this skill to fetch job data for digests and user queries.

## CRITICAL RULES — read before every DB query

1. **Never select `description_raw`** from the `jobs` table.
   This column contains full job posting text — it will blow the context window
   and violates the privacy rule. It is only read by Python scripts (Qwen).

2. **Allowed columns for agent queries:**
   ```
   jobs: id, url, title, company, location, remote, salary_raw,
         tags, score, score_reason, status, scraped_at, user_note
   ```

3. **Never expose raw profile data** from the `profile` table.
   The `raw_input` column is off-limits. Use `structured` and `preferences` only.

## Standard queries

### Daily digest (top scored jobs since last run)
```sql
SELECT title, company, location, remote, score, score_reason, tags, url,
       ROW_NUMBER() OVER (ORDER BY score DESC) AS display_num
FROM jobs
WHERE status = 'new'
  AND score >= (SELECT (preferences->>'min_score')::int FROM profile WHERE id = 1)
  AND scraped_at > NOW() - INTERVAL '24 hours'
ORDER BY score DESC
LIMIT (SELECT (preferences->>'digest_limit')::int FROM profile WHERE id = 1);
```

### Look up a specific job by display number (within today's digest)
Use the ROW_NUMBER from the digest query stored in session context.

### Mark a job as applied
```sql
UPDATE jobs SET status = 'applied', updated_at = NOW() WHERE id = $1;
```

### Mark a job as hidden (user not interested)
```sql
UPDATE jobs SET status = 'hidden', updated_at = NOW() WHERE id = $1;
```

### Add or update a note on a job
```sql
UPDATE jobs SET user_note = $1, updated_at = NOW() WHERE id = $2;
```

### Add or update a note on an application
```sql
UPDATE applications SET user_note = $1, updated_at = NOW() WHERE id = $2;
```

### Check budget remaining
```sql
SELECT
  (SELECT (preferences->>'together_budget_usd')::numeric
   FROM profile WHERE id = 1) -
  COALESCE((SELECT SUM(estimated_usd) FROM spend_log WHERE provider = 'together'), 0)
  AS remaining_usd;
```

## How to run queries
The agent can use the exec tool to call:
```bash
python scripts/db/query.py --sql "SELECT ..."
```
Or call the helper scripts directly for standard operations.
