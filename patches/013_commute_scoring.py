#!/usr/bin/env python3
"""
patches/013_commute_scoring.py
Adds commute time scoring via self-hosted OpenRouteService.

Changes:
  1. .env.example — add ORS_BASE_URL
  2. config/preferences.example.json — add commute preferences block
  3. db/migrations/004_commute.sql — add commute_minutes + commute_mode to jobs
  4. db/schema.sql — same columns
  5. scripts/commute/ors_client.py — new file (already created separately)
  6. scripts/commute/__init__.py — new file
  7. scripts/local_llm/score_jobs.py — call ORS after Qwen scoring
  8. skills/job-filter/filter_prompt.txt — include commute in scoring context
  9. skills/onboarding/SKILL.md — add commute + profile questions
  10. README.md — add public transport + docker-compose to roadmap
  11. CLAUDE.md — update

Run from workspace root:
    python3 patches/013_commute_scoring.py
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
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.exists() and f.read_text() == content:
        print(f"  ~ already exists: {description}")
    else:
        f.write_text(content)
        print(f"  ✓ {description}")
    OK += 1


def run_migration():
    global OK, FAIL
    print("  Running migration 004_commute.sql...")
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
        print(f"  ~ Nothing new to commit: {result.stdout.strip()}")


print("\n📋 Patch 013 — Commute scoring via OpenRouteService\n")

# ── 1. .env.example — add ORS_BASE_URL ───────────────────────────────────────
patch(
    ".env.example — add ORS_BASE_URL",
    ".env.example",
    "# SearXNG\nSEARXNG_URL=",
    "# OpenRouteService (self-hosted, for commute scoring)\n"
    "# Health check: $ORS_BASE_URL/ors/v2/health should return {\"status\":\"ready\"}\n"
    "ORS_BASE_URL=https://ors.example.com\n"
    "\n"
    "# SearXNG\nSEARXNG_URL=",
)

# ── 2. preferences.example.json — add commute block ──────────────────────────
patch(
    "config/preferences.example.json — add commute preferences",
    "config/preferences.example.json",
    '  "remote_preference": "both",',
    '  "remote_preference": "both",\n'
    '  "commute": {\n'
    '    "home_address": "5000 Odense C, Denmark",\n'
    '    "home_coords": null,\n'
    '    "max_minutes": 45,\n'
    '    "modes": ["driving-car"],\n'
    '    "target_arrival": "08:30"\n'
    '  },',
)

# ── 3. db/schema.sql — add commute columns to jobs ───────────────────────────
patch(
    "db/schema.sql — add commute_minutes and commute_mode to jobs",
    "db/schema.sql",
    "    user_note       TEXT,                      -- user's personal note on this job\n"
    "    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),",
    "    user_note       TEXT,                      -- user's personal note on this job\n"
    "    commute_minutes INTEGER,                   -- fastest commute in minutes (ORS)\n"
    "    commute_mode    VARCHAR(32),               -- e.g. 'driving-car', 'cycling-electric'\n"
    "    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),",
)

# ── 4. db/migrations/004_commute.sql ─────────────────────────────────────────
write_file(
    "db/migrations/004_commute.sql",
    "db/migrations/004_commute.sql",
    "-- migrations/004_commute.sql\n"
    "-- Adds commute_minutes and commute_mode columns to jobs table.\n"
    "\n"
    "ALTER TABLE jobs\n"
    "    ADD COLUMN IF NOT EXISTS commute_minutes INTEGER;\n"
    "\n"
    "ALTER TABLE jobs\n"
    "    ADD COLUMN IF NOT EXISTS commute_mode VARCHAR(32);\n"
    "\n"
    "INSERT INTO schema_migrations (version) VALUES ('004_commute')\n"
    "ON CONFLICT DO NOTHING;\n",
)

# ── 5. scripts/commute/__init__.py ────────────────────────────────────────────
write_file(
    "scripts/commute/__init__.py",
    "scripts/commute/__init__.py",
    "",
)

# ── 6. score_jobs.py — add commute lookup after Qwen scoring ─────────────────
patch(
    "score_jobs.py — import ORS client",
    "scripts/local_llm/score_jobs.py",
    "from scripts.local_llm.ollama_client import generate, is_available, OllamaError",
    "from scripts.local_llm.ollama_client import generate, is_available, OllamaError\n"
    "from scripts.commute.ors_client import (\n"
    "    get_best_commute, get_coordinates, is_available as ors_available, ORSError\n"
    ")",
)

patch(
    "score_jobs.py — load commute prefs and home coords",
    "scripts/local_llm/score_jobs.py",
    "    profile_summary, hard_requirements = load_profile_summary()",
    "    profile_summary, hard_requirements = load_profile_summary()\n"
    "\n"
    "    # Load commute preferences\n"
    "    _prefs_row = fetchone(\"SELECT preferences FROM profile WHERE id = 1\")\n"
    "    _prefs     = _prefs_row[\"preferences\"] if _prefs_row else {}\n"
    "    _commute   = _prefs.get(\"commute\", {})\n"
    "    _home_addr = _commute.get(\"home_address\")\n"
    "    _home_coords = None\n"
    "    _max_min   = _commute.get(\"max_minutes\", 45)\n"
    "    _modes     = _commute.get(\"modes\", [\"driving-car\"])\n"
    "    _ors_on    = ors_available() and bool(_home_addr)\n"
    "    if _ors_on:\n"
    "        try:\n"
    "            stored = _commute.get(\"home_coords\")\n"
    "            if stored:\n"
    "                _home_coords = tuple(stored)\n"
    "            else:\n"
    "                _home_coords = get_coordinates(_home_addr)\n"
    "            if not _home_coords:\n"
    "                print(f\"  ⚠ Could not geocode home address: {_home_addr}\")\n"
    "                _ors_on = False\n"
    "        except ORSError as e:\n"
    "            print(f\"  ⚠ ORS unavailable: {e}\")\n"
    "            _ors_on = False",
)

patch(
    "score_jobs.py — run commute lookup after scoring",
    "scripts/local_llm/score_jobs.py",
    "            print(f\"  ✓ {job['title']} @ {job['company']} — {score}/100\")\n"
    "            scored_ids.append(job_id_str)",
    "            # Commute calculation — skip for remote jobs or missing location\n"
    "            commute_minutes = None\n"
    "            commute_mode    = None\n"
    "            job_location = extracted_location or job.get(\"location\") or \"\"\n"
    "            is_remote    = extracted_remote or job.get(\"remote\") or False\n"
    "\n"
    "            if _ors_on and job_location and not is_remote:\n"
    "                try:\n"
    "                    commute_minutes, commute_mode = get_best_commute(\n"
    "                        _home_coords, job_location, _modes\n"
    "                    )\n"
    "                    if commute_minutes is not None:\n"
    "                        # Penalise score if commute exceeds max\n"
    "                        if commute_minutes > _max_min:\n"
    "                            penalty = min(20, (commute_minutes - _max_min) // 5 * 5)\n"
    "                            score   = max(0, score - penalty)\n"
    "                        execute(\"\"\"\n"
    "                            UPDATE jobs\n"
    "                            SET commute_minutes = %s, commute_mode = %s\n"
    "                            WHERE id = %s\n"
    "                        \"\"\", (commute_minutes, commute_mode, job_id_str))\n"
    "                        mode_label = commute_mode.replace('driving-car','🚗').replace('cycling-electric','⚡🚲').replace('cycling-regular','🚲').replace('foot-walking','🚶')\n"
    "                        print(f\"     🗺 {commute_minutes} min {mode_label}\")\n"
    "                except ORSError as e:\n"
    "                    print(f\"     ⚠ Commute lookup failed: {e}\")\n"
    "\n"
    "            print(f\"  ✓ {job['title']} @ {job['company']} — {score}/100\")\n"
    "            scored_ids.append(job_id_str)",
)

# ── 7. db-manager SKILL.md — add commute columns ─────────────────────────────
patch(
    "skills/db-manager/SKILL.md — add commute columns to allowed list",
    "skills/db-manager/SKILL.md",
    "   jobs: id, url, title, company, location, remote, salary_raw,\n"
    "         tags, score, score_reason, status, scraped_at, user_note",
    "   jobs: id, url, title, company, location, remote, salary_raw,\n"
    "         tags, score, score_reason, status, scraped_at, user_note,\n"
    "         commute_minutes, commute_mode",
)

# ── 8. AGENTS.md — show commute in digest ────────────────────────────────────
patch(
    "AGENTS.md — add commute to digest query and format",
    "AGENTS.md",
    "    SELECT title, company, location, remote, score, score_reason,\n"
    "           tags, url, user_note,",
    "    SELECT title, company, location, remote, score, score_reason,\n"
    "           tags, url, user_note, commute_minutes, commute_mode,",
)

patch(
    "AGENTS.md — show commute in digest format",
    "AGENTS.md",
    "   📍 [location] | [Remote if remote=True]\n"
    "   💬 [score_reason]\n"
    "   🔗 [url]\n"
    "   📝 [user_note — only if not None]",
    "   📍 [location] | [Remote if remote=True] | [commute_minutes min 🚗/🚲 if not null]\n"
    "   💬 [score_reason]\n"
    "   🔗 [url]\n"
    "   📝 [user_note — only if not None]",
)

# ── 9. onboarding SKILL.md — add commute + profile questions ─────────────────
patch(
    "skills/onboarding/SKILL.md — add extended profile questions",
    "skills/onboarding/SKILL.md",
    "### Step 4 — Preferences\n"
    "Ask 4 quick questions (one at a time is fine):\n"
    "1. What job titles are you looking for? (e.g. \"Backend Developer, Software Engineer\")\n"
    "2. What's your minimum monthly salary? (DKK or EUR)\n"
    "3. Preferred location(s) and remote preference?\n"
    "4. Any keywords to always exclude? (e.g. \"junior, unpaid\")",
    "### Step 4 — Preferences\n"
    "Ask these questions one at a time:\n"
    "1. What job titles are you looking for? (e.g. \"IT Administrator, Network Engineer\")\n"
    "2. What's your minimum monthly salary? (DKK or EUR)\n"
    "3. Remote, local, or both?\n"
    "4. Any keywords to always exclude? (e.g. \"junior, unpaid\")\n"
    "5. What's your full name? (for CV and cover letter)\n"
    "6. What's your LinkedIn profile URL?\n"
    "7. What's your home address or postcode? (for commute calculation and cover letter)\n"
    "8. How do you commute? (Car / Bicycle / E-bike / Walk — pick one or more)\n"
    "9. What's the maximum commute time you'd accept for an office job? (minutes)\n"
    "10. What time do you want to arrive at work? (e.g. 08:30)",
)

# ── 10. filter_prompt.txt — include commute context ──────────────────────────
patch(
    "skills/job-filter/filter_prompt.txt — add commute note",
    "skills/job-filter/filter_prompt.txt",
    "JOB POSTING:\n"
    "Title: {title}",
    "COMMUTE NOTE: Commute time is calculated separately after scoring.\n"
    "If location is clearly remote or work-from-home, set remote=true.\n"
    "If location is a city/address, extract it precisely for geocoding.\n"
    "\n"
    "JOB POSTING:\n"
    "Title: {title}",
)

# ── 11. README.md — add roadmap section ──────────────────────────────────────
patch(
    "README.md — add roadmap section",
    "README.md",
    "## License",
    """## Roadmap

### v2.1
- **Public transport commute** — Rejseplanen API (Denmark) for bus/train routing
- **Docker Compose installer** — one-command setup for SearXNG + OpenRouteService
- **docx/pdf documents** — proper Word and PDF CV/cover letter generation
- **Reply monitoring** — track application status from inbox

### Self-hosted stack (manual setup until Docker Compose installer)
- **SearXNG** — https://github.com/searxng/searxng-docker
- **OpenRouteService** — https://github.com/GIScience/openrouteservice
- **Ollama** — https://ollama.com

---

## License""",
)

# ── 12. CLAUDE.md — update ────────────────────────────────────────────────────
claude = WORKSPACE / "CLAUDE.md"
content = claude.read_text()
old = "- **Agent file write restrictions**"
new = ("- **Commute scoring** — ORS client in `scripts/commute/ors_client.py`. "
       "Called from `score_jobs.py` after Qwen scoring. 100km ORS limit means jobs "
       "beyond that get `commute_minutes=None`. Score penalised 5pts per 5min over `max_minutes`.\n"
       "- **Agent file write restrictions**")
if old in content:
    claude.write_text(content.replace(old, new))
    print("  ✓ CLAUDE.md — add commute scoring note")
    OK += 1
else:
    print("  ~ CLAUDE.md commute note — anchor not found, skipping")

# ── Run migration ─────────────────────────────────────────────────────────────
print()
run_migration()

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
print(f"✓ {OK} applied   ✗ {FAIL} failed")
if FAIL:
    sys.exit(1)

auto_commit(
    [
        ".env.example",
        "config/preferences.example.json",
        "db/schema.sql",
        "db/migrations/004_commute.sql",
        "scripts/commute/__init__.py",
        "scripts/commute/ors_client.py",
        "scripts/local_llm/score_jobs.py",
        "skills/db-manager/SKILL.md",
        "skills/job-filter/filter_prompt.txt",
        "skills/onboarding/SKILL.md",
        "AGENTS.md",
        "README.md",
        "CLAUDE.md",
        "patches/013_commute_scoring.py",
    ],
    "feat: commute scoring via OpenRouteService, extended onboarding profile"
)

print("\nNext steps:")
print("  1. Add ORS_BASE_URL to .env")
print("  2. python3 scripts/local_llm/score_jobs.py --rescore --limit 5")
print("     (verify commute times appear in output)")
print("  3. Restart gateway and run /onboard to add commute preferences")