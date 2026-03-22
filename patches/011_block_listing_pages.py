#!/usr/bin/env python3
"""
patches/011_block_listing_pages.py
Blocks job listing/category pages from SearXNG results.
These pages aggregate many jobs but aren't individual postings —
Qwen incorrectly scores them 53-75 because they contain job keywords.

Also updates CLAUDE.md to reflect current state.

Run from workspace root:
    python3 patches/011_block_listing_pages.py
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


print("\n📋 Patch 011 — Block listing pages in SearXNG + update CLAUDE.md\n")

# ── 1. Add listing page URL patterns to BLOCKED_PATH_FRAGMENTS ───────────────
patch(
    "searxng.py — block job listing/search category pages",
    "scripts/scraping/boards/searxng.py",
    "        \"/art/\",\n"
    "        \"/karriere/se-ledige-job\",\n"
    "    ]",
    "        \"/art/\",\n"
    "        \"/karriere/se-ledige-job\",\n"
    "        \"/jobsoegning\",          # Jobindex category pages\n"
    "        \"/find-job\",             # Jobnet category pages\n"
    "        \"-jobs\",                 # Careerjet/LinkedIn listing pages\n"
    "        \"/jobs/\",               # Generic job listing pages\n"
    "    ]",
)

# ── 2. Add listing page title patterns to BLOCKED_TITLE_FRAGMENTS ─────────────
patch(
    "searxng.py — block listing page titles",
    "scripts/scraping/boards/searxng.py",
    "        \"ledige job -\", \"se ledige job\",\n"
    "    ]",
    "        \"ledige job -\", \"se ledige job\",\n"
    "        \"jobs i danmark\", \"job i danmark\",  # Listing page titles\n"
    "        \"ledige stillinger fra\",              # Jobindex overview pages\n"
    "        \" nye) -\",                            # LinkedIn 'X nye job' listings\n"
    "        \"jobportal\",                          # HK jobportal etc.\n"
    "        \"den komplette guide\",                # Guide pages\n"
    "    ]",
)

# ── 3. Add careerjet and jobted to blocked domains ────────────────────────────
patch(
    "searxng.py — add aggregator domains to blocklist",
    "scripts/scraping/boards/searxng.py",
    "        \"jooble.org\", \"solidit.dk\",\n"
    "    }",
    "        \"jooble.org\", \"solidit.dk\",\n"
    "        \"careerjet.dk\", \"careerjet.com\",    # Aggregator — low quality\n"
    "        \"jobted.dk\",                          # Aggregator\n"
    "        \"jobsearch.dk\",                       # Aggregator\n"
    "        \"profic.dk\",                          # Guide/info site\n"
    "        \"hk.dk\",                              # Union portal, not job postings\n"
    "    }",
)

# ── 4. Update CLAUDE.md — patch system + current state ───────────────────────
claude_file = WORKSPACE / "CLAUDE.md"
content = claude_file.read_text()

# Update known issues section
old_issues = """## Known issues / current state

- **company/location** — extracted by Qwen during scoring (not from scraper). Run `--rescore` after adding new jobs to backfill.
- **SearXNG** — still returns some noise (category pages, municipality portals). Blocklists are iteratively improved.
- **Indeed** — disabled, 403 Forbidden. Covered by SearXNG.
- **IT-jobbank** — disabled, HTML selectors need updating.
- **Cron registration** — requires gateway to be running. Agent registers cron during `/onboard`."""

new_issues = """## Known issues / current state

- **company/location** — extracted by Qwen during scoring (not from scraper). Run `--rescore` after adding new jobs to backfill.
- **SearXNG** — blocklists iteratively improved via patches. time_range disabled when site_filter is set (combination returns 0 results).
- **Indeed** — disabled, 403 Forbidden. Covered by SearXNG.
- **IT-jobbank** — disabled, HTML selectors need updating.
- **Cron registration** — requires gateway to be running. Agent registers cron during `/onboard`.
- **raw.githubusercontent.com CDN lag** — up to 30 min behind actual commits. Always verify file state on the server, not via raw GitHub URLs."""

if old_issues in content:
    content = content.replace(old_issues, new_issues)
    print("  ✓ CLAUDE.md — updated known issues")
    OK += 1
else:
    print("  ~ CLAUDE.md known issues — anchor not found, skipping")

# Update patch system section
old_patch_section = "### Preferred: patch scripts\nAll changes should be made as numbered patch scripts in `patches/`.\nThis avoids regenerating whole files and reduces copy-paste errors."

new_patch_section = """### Preferred: patch scripts
All changes should be made as numbered patch scripts in `patches/`.
This avoids regenerating whole files and reduces copy-paste errors.

Key conventions:
- Patches include `auto_commit()` at the end — no manual git needed
- Large string content (e.g. AGENTS.md rewrites) goes in a separate `.txt` file
  to avoid Python triple-quote nesting issues (see patches/008_agents_content.txt)
- CLAUDE.md should be updated in patches when architecture changes
- `raw.githubusercontent.com` has CDN lag — verify changes on server not via raw URLs"""

if old_patch_section in content:
    content = content.replace(old_patch_section, new_patch_section)
    print("  ✓ CLAUDE.md — updated patch conventions")
    OK += 1
else:
    print("  ~ CLAUDE.md patch section — anchor not found, skipping")

claude_file.write_text(content)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
print(f"✓ {OK} applied   ✗ {FAIL} failed")
if FAIL:
    sys.exit(1)

auto_commit(
    [
        "scripts/scraping/boards/searxng.py",
        "CLAUDE.md",
        "patches/011_block_listing_pages.py",
    ],
    "fix: block SearXNG listing/category pages, update CLAUDE.md"
)

print("\nTest with:")
print("  python3 scripts/scraping/run_scrape.py --board searxng --dry-run")