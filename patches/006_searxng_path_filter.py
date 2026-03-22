#!/usr/bin/env python3
"""
patches/006_searxng_path_filter.py
Adds URL path filtering to SearXNG connector to block informational pages
(salary guides, blog posts, interview tips, job description articles)
that pass the domain filter but are not actual job postings.

Run from workspace root:
    python3 patches/006_searxng_path_filter.py
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


print("\n📋 Patch 006 — SearXNG URL path filtering\n")

# ── Add BLOCKED_DOMAINS and _is_valid_result if patch 005 wasn't applied ──────
searxng_path = WORKSPACE / "scripts/scraping/boards/searxng.py"
content = searxng_path.read_text()
has_blocked_domains = "BLOCKED_DOMAINS" in content

if not has_blocked_domains:
    # Patch 005 not applied — add full filter block
    patch_file(
        "searxng.py — add domain/title/path blocklist (005+006 combined)",
        "scripts/scraping/boards/searxng.py",
        "    def fetch(self, queries: list[str]) -> list[JobListing]:",
        """    BLOCKED_DOMAINS = {
        "facebook.com", "twitter.com", "x.com", "instagram.com",
        "youtube.com", "tiktok.com", "reddit.com", "quora.com",
        "wikipedia.org", "bitly.com", "bit.ly", "t.co",
        "microsoft.com", "google.com", "apple.com", "amazon.com",
        "translate.google.com", "rc-network.de",
        "naukri.com", "glassdoor.com", "glassdoor.co.uk", "glassdoor.co.in",
        "itjobswatch.co.uk", "builtin.com", "internshala.com",
        "netcomlearning.com", "simplilearn.com", "surftware.com",
        "nextinhr.com", "vinaligroup.com", "anjusmriti.com",
        "woman.dk", "akassedenmark.dk", "detsocialenetvaerk.dk",
        "ansogningshjaelpen.dk", "skrivsikkert.dk",
    }

    BLOCKED_PATH_FRAGMENTS = [
        "/salary", "/salaries", "/blog", "/article", "/articles",
        "/guide", "/guides", "/interview", "/interview-questions",
        "/job-description", "/job-descriptions", "/career-advice",
        "/news/", "/learn/", "/courses/", "/training/", "/certification/",
        "/about", "/contact", "/privacy", "/terms",
        "how-to", "what-is", "types-of",
    ]

    BLOCKED_TITLE_FRAGMENTS = [
        "traductor", "translate", "sign in", "log in", "create account",
        "short url", "url shortener", "how to", "what is", "suche",
        "salary", "salaries", "interview questions", "job description",
        "job vacancies in", "types of", "guide to", "tips for",
        "leder du efter", "her er", "7 steder",
    ]

    MIN_DESCRIPTION_LEN = 50

    def _is_valid_result(self, result: dict) -> bool:
        from urllib.parse import urlparse
        url   = result.get("url", "")
        title = result.get("title", "").lower()
        desc  = result.get("content", "")

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().lstrip("www.")
            path   = parsed.path.lower()

            if any(domain == b or domain.endswith("." + b)
                   for b in self.BLOCKED_DOMAINS):
                return False

            if any(frag in path for frag in self.BLOCKED_PATH_FRAGMENTS):
                return False
        except Exception:
            pass

        if any(frag in title for frag in self.BLOCKED_TITLE_FRAGMENTS):
            return False

        if len(desc) < self.MIN_DESCRIPTION_LEN:
            return False

        return True

    def fetch(self, queries: list[str]) -> list[JobListing]:""",
    )
else:
    # Patch 005 already applied — just add path filtering and extra domains
    patch_file(
        "searxng.py — expand blocked domains with noisy sites",
        "scripts/scraping/boards/searxng.py",
        '        "rc-network.de", "translate.google.com",\n'
        "    }",
        '        "rc-network.de", "translate.google.com",\n'
        '        "naukri.com", "glassdoor.com", "glassdoor.co.uk", "glassdoor.co.in",\n'
        '        "itjobswatch.co.uk", "builtin.com", "internshala.com",\n'
        '        "netcomlearning.com", "simplilearn.com", "surftware.com",\n'
        '        "nextinhr.com", "vinaligroup.com", "anjusmriti.com",\n'
        '        "woman.dk", "akassedenmark.dk", "detsocialenetvaerk.dk",\n'
        '        "ansogningshjaelpen.dk", "skrivsikkert.dk",\n'
        "    }",
    )

    patch_file(
        "searxng.py — add URL path fragment filter",
        "scripts/scraping/boards/searxng.py",
        "    BLOCKED_TITLE_FRAGMENTS = [",
        """    BLOCKED_PATH_FRAGMENTS = [
        "/salary", "/salaries", "/blog", "/article", "/articles",
        "/guide", "/guides", "/interview", "/interview-questions",
        "/job-description", "/job-descriptions", "/career-advice",
        "/news/", "/learn/", "/courses/", "/training/", "/certification/",
        "how-to", "what-is", "types-of",
    ]

    BLOCKED_TITLE_FRAGMENTS = [""",
    )

    patch_file(
        "searxng.py — apply path filter in _is_valid_result",
        "scripts/scraping/boards/searxng.py",
        "            if any(domain == b or domain.endswith(\".\" + b)\n"
        "                   for b in self.BLOCKED_DOMAINS):\n"
        "                return False\n"
        "        except Exception:\n"
        "            pass",
        "            if any(domain == b or domain.endswith(\".\" + b)\n"
        "                   for b in self.BLOCKED_DOMAINS):\n"
        "                return False\n"
        "\n"
        "            path = parsed.path.lower()\n"
        "            if any(frag in path for frag in self.BLOCKED_PATH_FRAGMENTS):\n"
        "                return False\n"
        "        except Exception:\n"
        "            pass",
    )

    patch_file(
        "searxng.py — expand blocked title fragments",
        "scripts/scraping/boards/searxng.py",
        '        "suche",\n'
        "    ]",
        '        "suche",\n'
        '        "salary", "salaries", "interview questions", "job description",\n'
        '        "job vacancies in", "types of", "guide to", "tips for",\n'
        '        "leder du efter", "her er", "7 steder",\n'
        "    ]",
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
    print("  git add scripts/scraping/boards/searxng.py patches/006_searxng_path_filter.py")
    print('  git commit -m "fix: SearXNG path filter, block salary/blog/guide pages"')