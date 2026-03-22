#!/usr/bin/env python3
"""
patches/002_explicit_digest.py
Adds an explicit digest query to AGENTS.md so the agent never needs to
explore the filesystem to figure out how to run /digest.
Also fixes the permitted exec commands to use python3.

Run from workspace root:
    python3 patches/002_explicit_digest.py
"""
import sys
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
OK   = 0
FAIL = 0


def patch(description: str, path: str, old: str, new: str):
    global OK, FAIL
    f = WORKSPACE / path
    if not f.exists():
        print(f"  ✗ FILE NOT FOUND: {path}")
        FAIL += 1
        return
    content = f.read_text()
    if new in content:
        print(f"  ~ already applied: {description}")
        OK += 1
        return
    if old not in content:
        print(f"  ✗ anchor not found: {description}")
        print(f"    Looking for: {old[:80]!r}...")
        FAIL += 1
        return
    f.write_text(content.replace(old, new, 1))
    print(f"  ✓ {description}")
    OK += 1


print("\n📋 Patch 002 — Explicit digest query + python3 fixes\n")

# ── 1. Fix permitted exec commands (python → python3) ────────────────────────
patch(
    "AGENTS.md — fix permitted exec commands to use python3",
    "AGENTS.md",
    """```
python scripts/scraping/run_scrape.py
python scripts/local_llm/score_jobs.py
python scripts/onboarding/parse_profile.py
python scripts/email/generate_application.py
python scripts/email/deliver_documents.py
python scripts/db/migrate.py
python scripts/db/check_budget.py
openclaw <subcommand>
```""",
    """```
python3 scripts/scraping/run_scrape.py
python3 scripts/local_llm/score_jobs.py
python3 scripts/onboarding/parse_profile.py
python3 scripts/email/generate_application.py
python3 scripts/email/deliver_documents.py
python3 scripts/db/migrate.py
python3 scripts/db/check_budget.py
openclaw <subcommand>  # includes: openclaw cron add/rm/list
```""",
)

# ── 2. Add explicit digest query ──────────────────────────────────────────────
patch(
    "AGENTS.md — add explicit digest SQL query",
    "AGENTS.md",
    "## Daily digest format\n\n```\n🦞 JobHunter",
    """## How to run the digest

When `/digest` is requested, run this exact query using the DB client — do NOT explore the filesystem:

```python
import sys; sys.path.insert(0, '.')
from scripts.db.client import fetchall
jobs = fetchall(\"\"\"
    SELECT title, company, location, remote, score, score_reason,
           tags, url, user_note,
           ROW_NUMBER() OVER (ORDER BY score DESC NULLS LAST) AS num
    FROM jobs
    WHERE status = 'new'
      AND scraped_at > NOW() - INTERVAL '7 days'
    ORDER BY score DESC NULLS LAST
    LIMIT 10
\"\"\")
for j in jobs: print(j)
```

Format each result using the digest format below and send to the user.
If no jobs found, say "No new matches in the last 7 days. Run /scrape to check for new jobs."

## Daily digest format

```
🦞 JobHunter""",
)

# ── 3. Add explicit /scrape instructions ─────────────────────────────────────
patch(
    "AGENTS.md — add explicit /scrape instructions",
    "AGENTS.md",
    "## Application flow",
    """## How to run a scrape

When `/scrape` is requested, run this command — nothing else:

```
python3 scripts/scraping/run_scrape.py
```

Wait for it to complete, then report: how many jobs were found and how many were new.
Do NOT read scraping scripts, do NOT explore the filesystem.

## Application flow""",
)

# ── 4. Fix /start → /onboard in command list ─────────────────────────────────
patch(
    "AGENTS.md — fix /start → /onboard in command list",
    "AGENTS.md",
    "- `/start`         — begin onboarding (also registers cron jobs on first run)",
    "- `/onboard`       — begin or redo onboarding",
)

# ── 5. Fix skill routing /start → /onboard ───────────────────────────────────
patch(
    "AGENTS.md — fix skill routing /start → /onboard",
    "AGENTS.md",
    "- `/start` or no profile → **onboarding** skill",
    "- `/onboard` or no profile → **onboarding** skill",
)

# ── 6. Add explicit do-not-explore rule ──────────────────────────────────────
patch(
    "AGENTS.md — add do-not-explore filesystem rule",
    "AGENTS.md",
    "## What you do NOT do",
    """## What you do NOT do

- **Explore the filesystem** — never read scripts, agent files, or docs to figure out how to do something. All instructions are in this file and the skill files.
- **Run `--help` commands** to discover tools — use only what is listed here.""",
)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
print(f"✓ {OK} applied   ✗ {FAIL} failed")
if FAIL:
    print("\nSome patches failed — check output above.")
    sys.exit(1)
else:
    print("\nAll done. Restart the gateway then test /digest.")
    print("\nCommit with:")
    print("  git add AGENTS.md patches/002_explicit_digest.py")
    print('  git commit -m "fix: explicit digest query, stop agent exploring filesystem"')