# JobHunter — Tool Notes

## Exec tool

Only the following commands are permitted. Do not attempt others.

```
python scripts/scraping/run_scrape.py [--board <slug>] [--dry-run]
python scripts/local_llm/score_jobs.py [--limit N] [--rescore] [--skip-dedup]
python scripts/onboarding/parse_profile.py --input <file>
python scripts/email/generate_application.py --job-id <uuid> [--force]
python scripts/email/deliver_documents.py --job-id <uuid>
python scripts/db/migrate.py
python scripts/db/check_budget.py
openclaw <subcommand>
```

## Database tool

Connect via `DATABASE_URL` from environment.
All queries go through `scripts/db/client.py`.

**Forbidden in queries:**
- `SELECT description_raw` — ever
- `SELECT raw_input FROM profile` — ever
- Any query writing to `spend_log` outside of `generate_application.py`

## File tool

Working directory is this workspace (`~/.openclaw/workspace-jobhunter`).

**Read freely:**
- `skills/` — skill instructions
- `config/preferences.json` — user preferences
- `scripts/` — script source

**Never read:**
- `.env` (one level up from workspace, in repo root)
- `~/.openclaw/openclaw.json`
- `~/.openclaw/credentials/`

**Write only to:**
- `tmp/` — staging area for generated documents (auto-cleaned)

## Telegram tool

Outbound messages go to the configured `TELEGRAM_USER_ID` only.
File attachments are sent via `deliver_documents.py` — not inline.
