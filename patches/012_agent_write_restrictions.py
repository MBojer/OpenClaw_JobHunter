#!/usr/bin/env python3
"""
patches/012_agent_write_restrictions.py
Tightens agent file write restrictions to prevent accidental or malicious
modification of core files (AGENTS.md, scripts/, skills/, patches/).

Changes:
  1. TOOLS.md — explicit hard rules on what agent can/cannot write
  2. AGENTS.md — add file write restriction rule
  3. config/openclaw.template.json — block git write commands in exec

Run from workspace root:
    python3 patches/012_agent_write_restrictions.py
"""
import sys
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
OK   = 0
FAIL = 0


def patch(description, path, old, new):
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
        print(f"    Looking for: {old[:70]!r}...")
        FAIL += 1
        return
    f.write_text(content.replace(old, new, 1))
    print(f"  ✓ {description}")
    OK += 1


def write_file(description, path, content):
    global OK
    f = WORKSPACE / path
    f.write_text(content)
    print(f"  ✓ {description}")
    OK += 1


def auto_commit(files, message):
    print("\n  Auto-committing...")
    for f in files:
        subprocess.run(["git", "add", f], cwd=WORKSPACE)
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=WORKSPACE, capture_output=True, text=True
    )
    if result.returncode == 0:
        push = subprocess.run(["git", "push"], cwd=WORKSPACE,
                              capture_output=True, text=True)
        if push.returncode == 0:
            print("  ✓ Committed and pushed")
        else:
            print(f"  ⚠ Committed but push failed: {push.stderr.strip()}")
    else:
        print(f"  ~ Nothing new to commit")


print("\n📋 Patch 012 — Agent file write restrictions\n")

# ── 1. Rewrite TOOLS.md with explicit write restrictions ─────────────────────
write_file(
    "TOOLS.md — explicit file write restrictions",
    "TOOLS.md",
    """# JobHunter — Tool Notes

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
""",
)

# ── 2. AGENTS.md — add file write restriction rule ───────────────────────────
patch(
    "AGENTS.md — add file write restriction as absolute rule",
    "AGENTS.md",
    "5. **Never explore the filesystem** to figure out how to do something.\n"
    "   All instructions are in this file and the skill files.\n"
    "   Never run `--help` commands to discover tools.",
    "5. **Never explore the filesystem** to figure out how to do something.\n"
    "   All instructions are in this file and the skill files.\n"
    "   Never run `--help` commands to discover tools.\n"
    "\n"
    "6. **Never modify core files.**\n"
    "   You may NOT write to: `AGENTS.md`, `SOUL.md`, `TOOLS.md`, `skills/`,\n"
    "   `scripts/`, `patches/`, `db/`, `install/`, `.env`.\n"
    "   You may write to: `tmp/`, `config/preferences.json`, `config/profile.json`, `USER.md`.\n"
    "   If a change is needed to core files, tell the user and ask them to do it.\n"
    "\n"
    "7. **Never run git write commands.**\n"
    "   `git add`, `git commit`, `git push` are forbidden.\n"
    "   Read-only git commands (`git status`, `git log`, `git diff`) are fine.",
)

# ── 3. Update openclaw.template.json exec blockedPatterns ────────────────────
patch(
    "config/openclaw.template.json — block git write commands",
    "config/openclaw.template.json",
    '        "python3 -c *"\n'
    "      ]\n"
    "    }\n"
    "  }\n"
    "}",
    '        "python3 -c *",\n'
    '        "git add*",\n'
    '        "git commit*",\n'
    '        "git push*",\n'
    '        "git reset*",\n'
    '        "git checkout*",\n'
    '        "git merge*",\n'
    '        "git rebase*"\n'
    "      ]\n"
    "    }\n"
    "  }\n"
    "}",
)

# ── 4. Update CLAUDE.md ───────────────────────────────────────────────────────
claude = WORKSPACE / "CLAUDE.md"
content = claude.read_text()
old = "- **raw.githubusercontent.com CDN lag** — up to 30 min behind actual commits. Always verify file state on the server, not via raw GitHub URLs."
new = ("- **raw.githubusercontent.com CDN lag** — up to 30 min behind actual commits. Always verify file state on the server, not via raw GitHub URLs.\n"
       "- **Agent file write restrictions** — agent may only write to `tmp/`, `config/preferences.json`, `config/profile.json`, `USER.md`. "
       "Core files (`AGENTS.md`, `scripts/`, `skills/`, etc.) are protected. Git write commands are blocked.")
if old in content:
    claude.write_text(content.replace(old, new))
    print("  ✓ CLAUDE.md — add agent write restriction note")
    OK += 1
else:
    print("  ~ CLAUDE.md — anchor not found, skipping")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
print(f"✓ {OK} applied   ✗ {FAIL} failed")
if FAIL:
    sys.exit(1)

auto_commit(
    [
        "TOOLS.md",
        "AGENTS.md",
        "config/openclaw.template.json",
        "CLAUDE.md",
        "patches/012_agent_write_restrictions.py",
    ],
    "security: restrict agent file writes and git commands"
)