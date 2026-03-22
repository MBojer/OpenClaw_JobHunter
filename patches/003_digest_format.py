#!/usr/bin/env python3
"""
patches/003_digest_format.py
Fixes digest display (location + score_reason on separate lines)
and tightens SearXNG to reduce junk results (Facebook, wrong countries).

Run from workspace root:
    python3 patches/003_digest_format.py
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


print("\n📋 Patch 003 — Fix digest format + SearXNG quality\n")

# ── 1. Fix digest query to include location clearly ───────────────────────────
patch(
    "AGENTS.md — fix digest format instructions",
    "AGENTS.md",
    "Format each result using the digest format below and send to the user.\n"
    'If no jobs found, say "No new matches in the last 7 days. Run /scrape to check for new jobs."',
    "Format each job result EXACTLY like this — field by field, never combine fields:\n"
    "```\n"
    "#[num] ⭐ [score] — [title] @ [company]\n"
    "   📍 [location] | [Remote if remote=True]\n"
    "   💬 [score_reason]\n"
    "   🔗 [url]\n"
    "   📝 [user_note — only if not None]\n"
    "```\n"
    "\n"
    "Rules:\n"
    "- 📍 line: location text only (e.g. \"Odense\" or \"Unknown\" if null)\n"
    "- 💬 line: score_reason text only — never on the same line as 📍\n"
    "- 📝 line: omit entirely if user_note is None or empty\n"
    'If no jobs found, say: "No new matches in the last 7 days. Run /scrape to check for new jobs."',
)

# ── 2. Fix digest format example block ───────────────────────────────────────
patch(
    "AGENTS.md — fix digest format example",
    "AGENTS.md",
    """```
🦞 JobHunter — [DATE]
[N] new matches today.

#1 ⭐ [score] — [Title] @ [Company]
   📍 [Location] | [remote tag if applicable]
   [score_reason — 1 sentence]
   🔗 [url]
   📝 [user_note — only if set]

#2 ...
```""",
    """```
🦞 JobHunter — [DATE]
[N] new matches today.

#1 ⭐ [score] — [Title] @ [Company]
   📍 [Location] | Remote
   💬 [score_reason — 1 sentence]
   🔗 [url]
   📝 [user_note — only show this line if a note exists]

#2 ...
```""",
)

# ── 3. Tighten SearXNG site_filter to DK/Nordic boards only ──────────────────
patch(
    "board_registry.json — tighten SearXNG site filter",
    "skills/job-scraper/board_registry.json",
    '"site_filter": "jobindex.dk OR it-jobbank.dk OR linkedin.com/jobs"',
    '"site_filter": "jobindex.dk OR it-jobbank.dk OR thehub.io OR jobnet.dk"',
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
    print("  git add AGENTS.md skills/job-scraper/board_registry.json patches/003_digest_format.py")
    print('  git commit -m "fix: digest format location+reason on separate lines, tighten SearXNG"')