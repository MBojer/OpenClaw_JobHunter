"""
scripts/scraping/boards/searxng.py
SearXNG connector — Tier 1 (JSON API)

Uses your self-hosted SearXNG instance to search multiple engines
simultaneously. Replaces Indeed (403) and supplements IT-jobbank (broken HTML).

Config keys in board_registry.json:
  base_url    — SearXNG instance URL (falls back to SEARXNG_URL env var)
  engines     — comma-separated engines to use (default: google,bing,duckduckgo)
  time_range  — week | month | year | None (default: month)
  language    — search language (default: da-DK)
  site_filter — optional site: filter e.g. "jobindex.dk OR it-jobbank.dk"
"""
import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.scraping.base_connector import BaseConnector, JobListing


class SearxngConnector(BaseConnector):
    """
    SearXNG JSON API connector.
    Searches multiple engines in one call per query.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = (
            config.get("base_url")
            or os.environ.get("SEARXNG_URL", "")
        ).rstrip("/")

        if not self.base_url:
            raise ValueError(
                "SearXNG base_url not set. Add SEARXNG_URL to .env "
                "or set base_url in board_registry.json"
            )

        self.engines     = config.get("engines", "google,bing,duckduckgo")
        self.time_range  = config.get("time_range", "month")
        self.language    = config.get("language", "da-DK")
        self.site_filter = config.get("site_filter", "")

    # Domains that never contain job postings
    BLOCKED_DOMAINS = {
        "facebook.com", "twitter.com", "x.com", "instagram.com",
        "youtube.com", "tiktok.com", "reddit.com", "quora.com",
        "wikipedia.org", "bitly.com", "bit.ly", "t.co",
        "microsoft.com", "google.com", "apple.com", "amazon.com",
        "accounts.google.com", "myaccount.microsoft.com",
        "rc-network.de", "translate.google.com",
        "naukri.com", "glassdoor.com", "glassdoor.co.uk", "glassdoor.co.in",
        "itjobswatch.co.uk", "builtin.com", "internshala.com",
        "netcomlearning.com", "simplilearn.com", "surftware.com",
        "nextinhr.com", "vinaligroup.com", "anjusmriti.com",
        "woman.dk", "akassedenmark.dk", "detsocialenetvaerk.dk",
        "ansogningshjaelpen.dk", "skrivsikkert.dk",
        "jooble.org", "solidit.dk",
    }

    # Title fragments that indicate non-job results
    BLOCKED_PATH_FRAGMENTS = [
        "/salary", "/salaries", "/blog", "/article", "/articles",
        "/guide", "/guides", "/interview", "/interview-questions",
        "/job-description", "/job-descriptions", "/career-advice",
        "/news/", "/learn/", "/courses/", "/training/", "/certification/",
        "how-to", "what-is", "types-of",
        "/art/", "/karriere/se-ledige-job",
    ]

    BLOCKED_TITLE_FRAGMENTS = [
        "traductor", "translate", "sign in", "log in", "create account",
        "short url", "url shortener", "link shortener", "how to",
        "what is", "suche", "recherche", "søg",
        "salary", "salaries", "interview questions", "job description",
        "job vacancies in", "types of", "guide to", "tips for",
        "leder du efter", "her er", "7 steder",
        "ledige job -", "se ledige job",
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

            path = parsed.path.lower()
            if any(frag in path for frag in self.BLOCKED_PATH_FRAGMENTS):
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

    def fetch(self, queries: list[str]) -> list[JobListing]:
        results = []
        seen_urls = set()

        for query in queries:
            if not query.strip():
                continue
            try:
                listings = self._search(query)
                new = [l for l in listings if l.url not in seen_urls]
                seen_urls.update(l.url for l in new)
                print(f"  [SearXNG] '{query}' → {len(listings)} results, {len(new)} unique")
                results.extend(new)
            except Exception as e:
                print(f"  [SearXNG] Error on query '{query}': {e}")

        return results

    def _search(self, query: str) -> list[JobListing]:
        # Build search query — append "job" and site filter if configured
        full_query = f"{query} stilling"
        if self.site_filter:
            full_query += f" ({self.site_filter})"

        params = {
            "q":          full_query,
            "format":     "json",
            "engines":    self.engines,
            "language":   self.language,
        }
        if self.time_range:
            params["time_range"] = self.time_range

        url = f"{self.base_url}/search?{urllib.parse.urlencode(params)}"
        headers = {
            "User-Agent": "JobHunter/2.0 (self-hosted SearXNG client)",
            "Accept":     "application/json",
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())

        return [
            self._parse_result(r)
            for r in data.get("results", [])
            if r.get("url") and self._is_valid_result(r)
        ]

    def _parse_result(self, result: dict) -> JobListing:
        # SearXNG publishedDate is not always present
        scraped_at = datetime.utcnow()
        if result.get("publishedDate"):
            try:
                from datetime import datetime as dt
                scraped_at = dt.fromisoformat(
                    result["publishedDate"].replace("Z", "+00:00")
                )
            except Exception:
                pass

        return JobListing(
            url             = result.get("url", ""),
            title           = result.get("title", ""),
            company         = "",           # SearXNG doesn't extract this — Qwen will
            location        = "",           # Same — Qwen extracts from description
            description_raw = result.get("content", ""),
            scraped_at      = scraped_at,
        )