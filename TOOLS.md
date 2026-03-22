# JobHunter — Tool Notes

## Exec tool

Only the following commands are permitted. Do not attempt others.

```
python3 scripts/scraping/run_scrape.py [--board <slug>] [--dry-run]
python3 scripts/local_llm/score_jobs.py [--limit N] [--rescore] [--skip-dedup]
python3 scripts/onboarding/parse_profile.py --input <file>
python3 scripts/email/generate_application.py --job-id <uuid> [--force]
python3 scripts/email/deliver_documents.py --job-id <uuid>
python3 scripts/db/migrate.py
python3 scripts/db/check_budget.py
openclaw cron add/rm/list
openclaw agents list
openclaw health
openclaw status
```

## File tool — READ permissions

You may read any file in the workspace.

## File tool — WRITE permissions (strict)

### ✅ YOU MAY WRITE TO:
- `tmp/` — document staging (CV/CL files before delivery)
- `config/preferences.json` — user preferences (updated by /boards and /onboard)
- `config/profile.json` — user profile (updated by /onboard)
- `USER.md` — user preferences note (updated by /onboard)

### ⛔ YOU MAY NEVER WRITE TO:
- `AGENTS.md` — your own operating instructions
- `SOUL.md` — your persona
- `TOOLS.md` — this file
- `IDENTITY.md` — your identity
- `HEARTBEAT.md` — heartbeat config
- `skills/` — any skill file
- `scripts/` — any Python script
- `patches/` — any patch file
- `db/` — schema or migration files
- `install/` — installer files
- `install.sh` — installer
- `.env` — secrets

If a task seems to require editing any of the above, tell the user and ask them
to make the change manually or via a patch script.

## Git tool

Read-only git commands are permitted:
```
git status
git log --oneline -10
git diff
git diff --stat origin/main
```

### ⛔ NEVER RUN:
- `git add`
- `git commit`
- `git push`
- `git reset`
- `git checkout`
- `git merge`
- `git rebase`

All commits are made by the user, not the agent.

## Database tool

Connect via `DATABASE_URL` from environment.
All queries go through `scripts/db/client.py`.

**Forbidden in queries:**
- `SELECT description_raw` — ever
- `SELECT raw_input FROM profile` — ever
- Any `DROP`, `TRUNCATE`, or `ALTER TABLE` statement

**Allowed writes:**
- `UPDATE jobs SET user_note`, `status`, `updated_at`
- `UPDATE profile SET preferences`, `structured`, `profile_hash`
- Standard inserts via scripts only

## Telegram tool

Outbound messages go to configured `TELEGRAM_USER_ID` only.
File attachments sent via `deliver_documents.py` — not inline.
