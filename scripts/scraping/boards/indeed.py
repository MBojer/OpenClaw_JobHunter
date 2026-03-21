"""
scripts/scraping/boards/indeed.py
Indeed Denmark — Tier 1 (RSS)
"""
import sys
import urllib.parse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.scraping.base_connector import BaseConnector, JobListing
from scripts.scraping.rss_connector import fetch_rss, rss_to_listings


class IndeedConnector(BaseConnector):
    """
    Indeed RSS connector.
    RSS URL: https://dk.indeed.com/rss?q={query}&l={location}&sort=date
    Location is read from preferences if available.
    """

    def fetch(self, queries: list[str]) -> list[JobListing]:
        results = []
        base_url = self.config.get(
            "rss_url",
            "https://dk.indeed.com/rss?q={query}&l=Denmark&sort=date"
        )

        for query in queries:
            try:
                url = base_url.format(
                    query=urllib.parse.quote(query),
                    location="Denmark",
                )
                items = fetch_rss(url)
                listings = rss_to_listings(items, self.config)
                print(f"  [Indeed] '{query}' → {len(listings)} jobs")
                results.extend(listings)
            except Exception as e:
                print(f"  [Indeed] Error on query '{query}': {e}")

        return results
