#!/usr/bin/env python3
"""
patches/009_boards_searxng.py
Updates /boards board discovery to use SearXNG instead of built-in web search.
The agent searches SearXNG directly via Python rather than the Brave tool.

Run from workspace root:
    python3 patches/009_boards_searxng.py
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


print("\n📋 Patch 009 — Board discovery via SearXNG instead of Brave\n")

# ── AGENTS.md — update board search to use SearXNG directly ──────────────────
patch(
    "AGENTS.md — use SearXNG for board discovery",
    "AGENTS.md",
    "3. On A — Search for boards:\n"
    "   - Ask: \"What field and country? (e.g. 'IT jobs Denmark' or 'remote software jobs')\"\n"
    "   - Search SearXNG: use web search for \"[query] job board site list\"\n"
    "   - Present results as a numbered list, excluding already-added boards\n"
    "   - User replies with numbers to add",
    "3. On A — Search for boards:\n"
    "   - Ask: \"What field and country? (e.g. 'IT jobs Denmark' or 'remote software jobs')\"\n"
    "   - Search SearXNG directly using this Python snippet:\n"
    "```python\n"
    "import sys, json, os, urllib.request, urllib.parse\n"
    "sys.path.insert(0, '.')\n"
    "from dotenv import load_dotenv; load_dotenv()\n"
    "base = os.environ.get('SEARXNG_URL', 'http://localhost')\n"
    "q = urllib.parse.urlencode({'q': '[USER_QUERY] job board list', 'format': 'json', 'language': 'en'})\n"
    "req = urllib.request.Request(f'{base}/search?{q}', headers={'Accept': 'application/json'})\n"
    "data = json.loads(urllib.request.urlopen(req, timeout=10).read())\n"
    "results = [(r['title'], r['url']) for r in data.get('results', [])[:15]]\n"
    "print(json.dumps(results))\n"
    "```\n"
    "   - Extract domain names from the URLs returned\n"
    "   - Filter out any already in the user's board list\n"
    "   - Present as a numbered list for the user to pick from\n"
    "   - User replies with numbers to add",
)

# ── Also update the onboarding skill to use SearXNG ──────────────────────────
patch(
    "skills/onboarding/SKILL.md — use SearXNG for board discovery",
    "skills/onboarding/SKILL.md",
    "Then search for relevant job boards using web search:\n"
    "- For remote: search \"best remote job boards [field]\"\n"
    "- For local: search \"job boards [country] [field]\"\n"
    "- For both: search both",
    "Then search for relevant job boards using SearXNG directly:\n"
    "```python\n"
    "import sys, json, os, urllib.request, urllib.parse\n"
    "sys.path.insert(0, '.')\n"
    "from dotenv import load_dotenv; load_dotenv()\n"
    "base = os.environ.get('SEARXNG_URL', 'http://localhost')\n"
    "# Adjust query based on remote/local preference\n"
    "query = 'best remote job boards software' # or 'job boards Denmark IT'\n"
    "q = urllib.parse.urlencode({'q': query, 'format': 'json', 'language': 'en'})\n"
    "req = urllib.request.Request(f'{base}/search?{q}', headers={'Accept': 'application/json'})\n"
    "data = json.loads(urllib.request.urlopen(req, timeout=10).read())\n"
    "results = [(r['title'], r['url']) for r in data.get('results', [])[:15]]\n"
    "print(json.dumps(results))\n"
    "```\n"
    "Extract domain names from URLs and present as a numbered list.",
)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
print(f"✓ {OK} applied   ✗ {FAIL} failed")
if FAIL:
    print("\nSome patches failed — check output above.")
    sys.exit(1)
else:
    print("\nAll done. Restart gateway and test /boards → A again.")
    print("\nCommit with:")
    print("  git add AGENTS.md skills/onboarding/SKILL.md patches/009_boards_searxng.py")
    print('  git commit -m "fix: board discovery uses SearXNG instead of Brave web search"')
    print("  git push")