#!/usr/bin/env python3
"""
patches/010_searxng_timerange.py
Fixes SearXNG returning 0 results when time_range is combined with site_filter.
The combination of time_range=month + long OR site filter causes search engines
to return nothing. Removing time_range fixes it — freshness is handled by
scraped_at timestamp and Qwen scoring instead.

Run from workspace root:
    python3 patches/010_searxng_timerange.py
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


print("\n📋 Patch 010 — Fix SearXNG time_range + site_filter returning 0 results\n")

# ── Remove time_range when site_filter is active ──────────────────────────────
patch(
    "searxng.py — don't send time_range when site_filter is set",
    "scripts/scraping/boards/searxng.py",
    "        if self.time_range:\n"
    "            params[\"time_range\"] = self.time_range",
    "        # time_range + site_filter combined causes 0 results from most engines\n"
    "        # Only send time_range when there is no site_filter\n"
    "        if self.time_range and not self.site_filter:\n"
    "            params[\"time_range\"] = self.time_range",
)

print(f"\n{'─'*50}")
print(f"✓ {OK} applied   ✗ {FAIL} failed")
if FAIL:
    sys.exit(1)

auto_commit(
    ["scripts/scraping/boards/searxng.py", "patches/010_searxng_timerange.py"],
    "fix: SearXNG skip time_range when site_filter set — fixes 0 results"
)

print("\nTest with:")
print("  python3 scripts/scraping/run_scrape.py --board searxng --dry-run")