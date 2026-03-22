#!/usr/bin/env python3
"""
patches/008_job_boards.py
Adds dynamic job board management:
  - Board discovery during onboarding (SearXNG search)
  - /boards command for managing boards after setup
  - Custom board URL support
  - site_filter driven by preferences.json instead of hardcoded in board_registry.json
  - run_scrape.py reads site_filter from preferences

Also syncs AGENTS.md to its correct state (patches 002/003 were never committed).

Run from workspace root:
    python3 patches/008_job_boards.py
"""
import sys
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


print("\n📋 Patch 008 — Dynamic job board management + AGENTS.md sync\n")

# ── 1. AGENTS.md — write from content file to avoid triple-quote nesting ─────
agents_content_file = WORKSPACE / "patches" / "008_agents_content.txt"
if not agents_content_file.exists():
    print("  ✗ patches/008_agents_content.txt not found — cannot update AGENTS.md")
    FAIL += 1
else:
    new_content = agents_content_file.read_text()
    agents_file = WORKSPACE / "AGENTS.md"
    current = agents_file.read_text()
    if "/boards" in current and "job_boards" in current:
        print("  ~ already applied: AGENTS.md — full sync")
        OK += 1
    else:
        agents_file.write_text(new_content)
        print("  ✓ AGENTS.md — full sync (python3, /onboard, /boards, digest query)")
        OK += 1

# ── 2. onboarding SKILL.md — add board discovery step ────────────────────────
patch(
    "skills/onboarding/SKILL.md — add board discovery after preferences",
    "skills/onboarding/SKILL.md",
    "### Step 6 — Register cron jobs",
    """### Step 6 — Discover job boards
Ask the user two questions:
1. "Are you looking for remote, local, or both?"
2. "Which country or region?" (skip if remote only)

Then search for relevant job boards using web search:
- For remote: search "best remote job boards [field]"
- For local: search "job boards [country] [field]"
- For both: search both

Present up to 10 results as a numbered list:
```
Here are job boards I found. Reply with the numbers you want,
ALL for all of them, or NONE to skip:

1. remoteok.com — Remote jobs worldwide
2. weworkremotely.com — Remote jobs
3. jobindex.dk — Danish jobs
4. it-jobbank.dk — Danish IT jobs
...
```

Save selected boards to preferences:
```python
prefs['job_boards'] = ["remoteok.com", "jobindex.dk", ...]
prefs['remote_preference'] = "remote" | "local" | "both"
```

Tell user: "You can manage boards anytime with /boards"

### Step 7 — Register cron jobs""",
)

# ── 3. onboarding SKILL.md — renumber final steps ────────────────────────────
patch(
    "skills/onboarding/SKILL.md — renumber finish step",
    "skills/onboarding/SKILL.md",
    "### Step 7 — Finish",
    "### Step 8 — Finish",
)

# ── 4. preferences.example.json — add job_boards field ───────────────────────
patch(
    "config/preferences.example.json — add job_boards and remote_preference",
    "config/preferences.example.json",
    '  "delivery": {',
    '  "remote_preference": "both",\n'
    '  "job_boards": [\n'
    '    "remoteok.com",\n'
    '    "weworkremotely.com",\n'
    '    "jobindex.dk",\n'
    '    "it-jobbank.dk",\n'
    '    "thehub.io"\n'
    '  ],\n'
    '  "delivery": {',
)

# ── 5. board_registry.json — remove hardcoded site_filter ────────────────────
patch(
    "board_registry.json — remove hardcoded site_filter (now from preferences)",
    "skills/job-scraper/board_registry.json",
    '"site_filter": "jobindex.dk OR it-jobbank.dk OR thehub.io OR jobnet.dk"',
    '"site_filter": ""',
)

# ── 6. run_scrape.py — add searxng to CONNECTOR_MAP ──────────────────────────
patch(
    "run_scrape.py — add searxng to CONNECTOR_MAP",
    "scripts/scraping/run_scrape.py",
    '"jobindex":   "scripts.scraping.boards.jobindex.JobindexConnector",\n'
    '    "indeed":     "scripts.scraping.boards.indeed.IndeedConnector",',
    '"jobindex":   "scripts.scraping.boards.jobindex.JobindexConnector",\n'
    '    "searxng":    "scripts.scraping.boards.searxng.SearxngConnector",\n'
    '    "indeed":     "scripts.scraping.boards.indeed.IndeedConnector",',
)

# ── 7. run_scrape.py — add load_site_filter function ─────────────────────────
patch(
    "run_scrape.py — add load_site_filter() from preferences",
    "scripts/scraping/run_scrape.py",
    "def url_exists(url: str) -> bool:",
    """def load_site_filter() -> str:
    \"\"\"Build site_filter from user's selected job boards in preferences.\"\"\"
    row = fetchone("SELECT preferences FROM profile WHERE id = 1")
    if not row or not row["preferences"]:
        return ""
    boards = row["preferences"].get("job_boards", [])
    return " OR ".join(boards) if boards else ""


def url_exists(url: str) -> bool:""",
)

# ── 8. run_scrape.py — inject site_filter into SearXNG config ────────────────
patch(
    "run_scrape.py — inject site_filter into SearXNG at scrape time",
    "scripts/scraping/run_scrape.py",
    "        try:\n"
    "            connector = load_connector(slug, board)\n"
    "            listings  = connector.fetch(queries)",
    "        try:\n"
    "            # Inject user's job board list as site_filter for SearXNG\n"
    "            if slug == 'searxng':\n"
    "                site_filter = load_site_filter()\n"
    "                if site_filter:\n"
    "                    board = dict(board)\n"
    "                    board['site_filter'] = site_filter\n"
    "\n"
    "            connector = load_connector(slug, board)\n"
    "            listings  = connector.fetch(queries)",
)

# ── 9. run_scrape.py — fix local-llm path bug ────────────────────────────────
patch(
    "run_scrape.py — fix local-llm → local_llm path",
    "scripts/scraping/run_scrape.py",
    '"scripts/local-llm/score_jobs.py"',
    '"scripts/local_llm/score_jobs.py"',
)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
print(f"✓ {OK} applied   ✗ {FAIL} failed")
if FAIL:
    print("\nSome patches failed — check output above.")
    sys.exit(1)
else:
    print("\nAll done. Restart gateway to pick up AGENTS.md changes.")
    print("\nCommit with:")
    print("  git add AGENTS.md patches/008_agents_content.txt patches/008_job_boards.py")
    print("  git add skills/onboarding/SKILL.md config/preferences.example.json")
    print("  git add skills/job-scraper/board_registry.json scripts/scraping/run_scrape.py")
    print('  git commit -m "feat: dynamic job board management, /boards command"')
    print("  git push")