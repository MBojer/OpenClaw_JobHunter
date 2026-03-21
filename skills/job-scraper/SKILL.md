# Skill: Job Scraper

## Purpose
Fetch new job postings from all active boards and store them in the database.
Scoring is handled separately by the job-filter skill after scraping completes.

## When to use this skill
- Triggered by cron (see `cron/schedule.md`)
- User asks to "scrape now" or "check for new jobs"

## How to run a scrape

```bash
python scripts/scraping/run_scrape.py
```

Optional flags:
- `--board jobindex` — scrape a single board
- `--dry-run` — print what would be scraped without saving to DB

## What happens
1. `run_scrape.py` reads `skills/job-scraper/board_registry.json`
2. For each enabled board, instantiates the correct connector
3. Each connector fetches jobs and returns a standardised list
4. Deduplication: jobs with a URL already in the `jobs` table are skipped
5. New jobs are inserted with `status='new'` and `score=NULL`
6. A row is written to `run_log`

## Adding a new board
See `docs/adding-a-board.md`. Copy `scripts/scraping/boards/_template.py`.

## Rules
- Never pass raw job descriptions to the orchestrator or any chat message
- Deduplication is URL-based — always check before inserting
- Log all runs to `run_log` including errors
- If a single board fails, continue with remaining boards (partial run = status "partial")
