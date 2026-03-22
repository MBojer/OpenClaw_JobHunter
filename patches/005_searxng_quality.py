#!/usr/bin/env python3
"""
patches/005_searxng_quality.py
Improves SearXNG result quality by:
  1. Adding a URL blocklist to filter obvious non-job domains
  2. Adding a title blocklist to filter non-job titles
  3. Requiring a minimum description length
  4. Changing query from "job title job" to "job title ledige stillinger" (Danish)

Run from workspace root:
    python3 patches/005_searxng_quality.py
"""
import sys
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
OK   = 0
FAIL = 0


def patch_file(description, path, old, new):
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


print("\n📋 Patch 005 — SearXNG result quality filters\n")

# ── 1. Add blocklist and quality filters to searxng.py ───────────────────────
patch_file(
    "searxng.py — add URL/title blocklist and min description length",
    "scripts/scraping/boards/searxng.py",
    "    def fetch(self, queries: list[str]) -> list[JobListing]:",
    """    # Domains that never contain job postings
    BLOCKED_DOMAINS = {
        "facebook.com", "twitter.com", "x.com", "instagram.com",
        "youtube.com", "tiktok.com", "reddit.com", "quora.com",
        "wikipedia.org", "bitly.com", "bit.ly", "t.co",
        "microsoft.com", "google.com", "apple.com", "amazon.com",
        "accounts.google.com", "myaccount.microsoft.com",
        "rc-network.de", "translate.google.com",
    }

    # Title fragments that indicate non-job results
    BLOCKED_TITLE_FRAGMENTS = [
        "traductor", "translate", "sign in", "log in", "create account",
        "short url", "url shortener", "link shortener", "how to",
        "what is", "suche", "recherche", "søg",
    ]

    MIN_DESCRIPTION_LEN = 50  # Characters — anything shorter is a nav link, not a job

    def _is_valid_result(self, result: dict) -> bool:
        url   = result.get("url", "")
        title = result.get("title", "").lower()
        desc  = result.get("content", "")

        # Block by domain
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower().lstrip("www.")
            if any(domain == b or domain.endswith("." + b)
                   for b in self.BLOCKED_DOMAINS):
                return False
        except Exception:
            pass

        # Block by title fragment
        if any(frag in title for frag in self.BLOCKED_TITLE_FRAGMENTS):
            return False

        # Require minimum description length
        if len(desc) < self.MIN_DESCRIPTION_LEN:
            return False

        return True

    def fetch(self, queries: list[str]) -> list[JobListing]:""",
)

# ── 2. Apply the filter in _search() ─────────────────────────────────────────
patch_file(
    "searxng.py — apply _is_valid_result filter",
    "scripts/scraping/boards/searxng.py",
    "        return [\n"
    "            self._parse_result(r)\n"
    "            for r in data.get(\"results\", [])\n"
    "            if r.get(\"url\")\n"
    "        ]",
    "        return [\n"
    "            self._parse_result(r)\n"
    "            for r in data.get(\"results\", [])\n"
    "            if r.get(\"url\") and self._is_valid_result(r)\n"
    "        ]",
)

# ── 3. Improve query — add Danish job keywords ────────────────────────────────
patch_file(
    "searxng.py — improve query with Danish job keywords",
    "scripts/scraping/boards/searxng.py",
    '        full_query = f"{query} job"\n'
    "        if self.site_filter:",
    '        full_query = f"{query} stilling"\n'
    "        if self.site_filter:",
)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
print(f"✓ {OK} applied   ✗ {FAIL} failed")
if FAIL:
    print("\nSome patches failed — check output above.")
    sys.exit(1)
else:
    print("\nAll done. Test with:")
    print("  python3 scripts/scraping/run_scrape.py --board searxng --dry-run")
    print("\nCommit with:")
    print("  git add scripts/scraping/boards/searxng.py patches/005_searxng_quality.py")
    print('  git commit -m "fix: SearXNG domain/title blocklist, min description length, better query"')