#!/usr/bin/env python3
"""
patches/001_notes.py
Adds user notes to jobs and applications.

Run from workspace root:
    python3 patches/001_notes.py

What this does:
  1. db/schema.sql          — add user_note to jobs and applications tables
  2. db/migrations/003_notes.sql — create migration file for existing installs
  3. AGENTS.md              — add /note command and digest format update
  4. skills/db-manager/SKILL.md — add user_note to allowed columns
  5. Runs the migration against the live DB
"""
import sys
import subprocess
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
        print(f"    Looking for: {old[:60]!r}...")
        FAIL += 1
        return
    f.write_text(content.replace(old, new, 1))
    print(f"  ✓ {description}")
    OK += 1


def create_file(description: str, path: str, content: str):
    global OK, FAIL
    f = WORKSPACE / path
    if f.exists():
        print(f"  ~ already exists: {description}")
        OK += 1
        return
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content)
    print(f"  ✓ created: {description}")
    OK += 1


def run_migration():
    global OK, FAIL
    print("  Running migration 003_notes.sql...")
    result = subprocess.run(
        [sys.executable, "scripts/db/migrate.py"],
        capture_output=True, text=True, cwd=WORKSPACE
    )
    if result.returncode == 0:
        print("  ✓ Migration applied")
        OK += 1
    else:
        print(f"  ✗ Migration failed:\n{result.stdout}\n{result.stderr}")
        FAIL += 1


print("\n📋 Patch 001 — User notes on jobs and applications\n")

# ── 1. db/schema.sql — add user_note to jobs ─────────────────────────────────
patch(
    "db/schema.sql — add user_note to jobs table",
    "db/schema.sql",
    "    duplicate_of    UUID REFERENCES jobs(id),  -- set when status='duplicate'\n"
    "    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),",
    "    duplicate_of    UUID REFERENCES jobs(id),  -- set when status='duplicate'\n"
    "    user_note       TEXT,                      -- user's personal note on this job\n"
    "    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),",
)

# ── 2. db/schema.sql — add user_note to applications ─────────────────────────
patch(
    "db/schema.sql — add user_note to applications table",
    "db/schema.sql",
    "    delivered_at    TIMESTAMPTZ,\n"
    "    notes           TEXT,\n"
    "    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()\n"
    ");",
    "    delivered_at    TIMESTAMPTZ,\n"
    "    notes           TEXT,\n"
    "    user_note       TEXT,                      -- user's personal note on this application\n"
    "    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()\n"
    ");",
)

# ── 3. db/migrations/003_notes.sql ───────────────────────────────────────────
create_file(
    "db/migrations/003_notes.sql",
    "db/migrations/003_notes.sql",
    """-- migrations/003_notes.sql
-- Adds user_note column to jobs and applications tables.

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS user_note TEXT;

ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS user_note TEXT;

INSERT INTO schema_migrations (version) VALUES ('003_notes')
ON CONFLICT DO NOTHING;
""",
)

# ── 4. skills/db-manager/SKILL.md — add user_note to allowed columns ─────────
patch(
    "skills/db-manager/SKILL.md — add user_note to allowed columns",
    "skills/db-manager/SKILL.md",
    "   jobs: id, url, title, company, location, remote, salary_raw,\n"
    "         tags, score, score_reason, status, scraped_at",
    "   jobs: id, url, title, company, location, remote, salary_raw,\n"
    "         tags, score, score_reason, status, scraped_at, user_note",
)

# ── 4b. skills/db-manager/SKILL.md — add note queries ────────────────────────
patch(
    "skills/db-manager/SKILL.md — add note queries",
    "skills/db-manager/SKILL.md",
    "### Check budget remaining",
    """### Add or update a note on a job
```sql
UPDATE jobs SET user_note = $1, updated_at = NOW() WHERE id = $2;
```

### Add or update a note on an application
```sql
UPDATE applications SET user_note = $1, updated_at = NOW() WHERE id = $2;
```

### Check budget remaining""",
)

# ── 5. AGENTS.md — add /note command to command list ─────────────────────────
patch(
    "AGENTS.md — add /note to command list",
    "AGENTS.md",
    "- `/redeliver [N]` — redeliver existing documents for job #N\n"
    "- `/help`          — show this list",
    "- `/redeliver [N]` — redeliver existing documents for job #N\n"
    "- `/note [N] [text]` — add a note to job #N from the latest digest\n"
    "- `/help`          — show this list",
)

# ── 6. AGENTS.md — add note handling instructions ────────────────────────────
patch(
    "AGENTS.md — add note handling instructions",
    "AGENTS.md",
    "- `/scrape`                → `python3 scripts/scraping/run_scrape.py`\n"
    "- DB queries               → **db-manager** skill rules strictly",
    "- `/scrape`                → `python3 scripts/scraping/run_scrape.py`\n"
    "- `/note N text`           → UPDATE jobs SET user_note = 'text' WHERE id = <job_uuid>\n"
    "- DB queries               → **db-manager** skill rules strictly",
)

# ── 7. AGENTS.md — update digest format to show notes ────────────────────────
patch(
    "AGENTS.md — show user_note in digest format",
    "AGENTS.md",
    "#1 ⭐ [score] — [Title] @ [Company]\n"
    "   📍 [Location] | [remote tag if applicable]\n"
    "   [score_reason — 1 sentence]\n"
    "   🔗 [url]",
    "#1 ⭐ [score] — [Title] @ [Company]\n"
    "   📍 [Location] | [remote tag if applicable]\n"
    "   [score_reason — 1 sentence]\n"
    "   🔗 [url]\n"
    "   📝 [user_note — only if set]",
)

# ── 8. Run DB migration ───────────────────────────────────────────────────────
print()
run_migration()

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
print(f"✓ {OK} applied   ✗ {FAIL} failed")
if FAIL:
    print("\nSome patches failed — check output above.")
    sys.exit(1)
else:
    print("\nAll done. Commit with:")
    print("  git add db/schema.sql db/migrations/003_notes.sql")
    print("  git add skills/db-manager/SKILL.md AGENTS.md patches/001_notes.py")
    print('  git commit -m "feat: user notes on jobs and applications"')