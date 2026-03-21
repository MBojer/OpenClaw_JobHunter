# Skill: Job Filter

## Purpose
Score unscored jobs against the user's profile using the local Qwen2.5:7b model.
After scoring, runs a dedup pass to detect cross-posted jobs from the same company.
Runs after each scrape. Results are stored in the database.

## When to use this skill
- Triggered automatically after `run_scrape.py` completes
- User asks to "re-score jobs" or "rescore"

## How to run scoring + dedup

```bash
python scripts/local_llm/score_jobs.py
```

Optional flags:
- `--limit 20`     — score at most N jobs per run (default: all unscored)
- `--rescore`      — re-score already-scored jobs (useful after profile update)
- `--job-id <uuid>` — score a single specific job
- `--skip-dedup`   — skip the dedup pass (faster, use when debugging scoring only)

## What happens — two passes

### Pass 1: Scoring
1. Queries DB: `SELECT id, title, company, location, description_raw FROM jobs WHERE score IS NULL`
2. For each job: builds prompt from `skills/job-filter/filter_prompt.txt`
3. Sends to Qwen2.5:7b via Ollama
4. Parses response: score (0-100), tags, one-line reason
5. Updates `jobs` table: `score`, `tags`, `score_reason`, `scored_at`

### Pass 2: Deduplication (runs after all scoring completes)
1. For each newly scored job, queries other jobs from the same company (last 30 days)
2. If any candidates exist: asks Qwen "are these the same posting?"
3. If YES: marks the newer job as `status='duplicate'`, sets `duplicate_of` to the original
4. Uses `dedup_prompt.txt` — temperature 0.0 for deterministic answers
5. When uncertain, Qwen answers NO (conservative — better to show a duplicate than miss a job)

## Score meaning
- 90-100: Excellent match — always in digest
- 70-89:  Good match — include if slots available
- 50-69:  Partial match — include only if few high-score jobs
- 0-49:   Poor match — excluded from digest

## Rules
- `description_raw` is used here by Qwen — this is correct and expected
- Scores and dedup results are never passed to the free model verbatim
- If Ollama is unreachable, log and exit gracefully
- Duplicates are kept in DB with `status='duplicate'` — never deleted
