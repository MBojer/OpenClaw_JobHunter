"""
scripts/scraping/boards/it_jobbank.py
IT-jobbank.dk — Tier 2 (HTML scraper)
Uses only stdlib — no BeautifulSoup dependency.
"""
import sys
import re
import html
import urllib.request
import urllib.parse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.scraping.base_connector import BaseConnector, JobListing

BASE_URL = "https://www.it-jobbank.dk/jobsoegning"
HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; JobHunter/2.0)"}


class ItJobbankConnector(BaseConnector):
    """
    IT-jobbank.dk HTML scraper (Tier 2).
    Parses search result pages using regex + stdlib html.parser.
    NOTE: Update selectors if the site changes layout.
    """

    def fetch(self, queries: list[str]) -> list[JobListing]:
        results = []
        for query in queries:
            try:
                listings = self._fetch_query(query)
                print(f"  [IT-jobbank] '{query}' → {len(listings)} jobs")
                results.extend(listings)
            except Exception as e:
                print(f"  [IT-jobbank] Error on query '{query}': {e}")
        return results

    def _fetch_query(self, query: str) -> list[JobListing]:
        url = f"{BASE_URL}?text={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers=HEADERS)

        with urllib.request.urlopen(req, timeout=15) as resp:
            page_html = resp.read().decode("utf-8", errors="replace")

        return self._parse_listings(page_html)

    def _parse_listings(self, page_html: str) -> list[JobListing]:
        """
        Extract job listings from HTML.
        Targets: <article class="..."> blocks containing job cards.
        This is brittle by nature — update if layout changes.
        """
        listings = []

        # Match job card article blocks
        cards = re.findall(
            r'<article[^>]*class="[^"]*job[^"]*"[^>]*>(.*?)</article>',
            page_html,
            re.DOTALL | re.IGNORECASE,
        )

        for card in cards:
            url     = self._extract_href(card)
            title   = self._extract_text(card, r'<h2[^>]*>(.*?)</h2>')
            company = self._extract_text(card, r'class="[^"]*company[^"]*"[^>]*>(.*?)<')

            if not url or not title:
                continue

            # Make URL absolute
            if url.startswith("/"):
                url = "https://www.it-jobbank.dk" + url

            listings.append(JobListing(
                url     = url,
                title   = html.unescape(title).strip(),
                company = html.unescape(company).strip() if company else "",
            ))

        return listings

    def _extract_href(self, html_fragment: str) -> str:
        match = re.search(r'href="(/job/[^"]+)"', html_fragment)
        return match.group(1) if match else ""

    def _extract_text(self, html_fragment: str, pattern: str) -> str:
        match = re.search(pattern, html_fragment, re.DOTALL | re.IGNORECASE)
        if not match:
            return ""
        return re.sub(r"<[^>]+>", "", match.group(1)).strip()
