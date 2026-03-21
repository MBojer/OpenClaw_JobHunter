"""
scripts/scraping/boards/jobindex.py
Jobindex.dk — Tier 1 (RSS)
"""
import sys
import urllib.parse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.scraping.base_connector import BaseConnector, JobListing
from scripts.scraping.rss_connector import fetch_rss, rss_to_listings


class JobindexConnector(BaseConnector):
    """
    Jobindex.dk RSS connector.
    RSS URL pattern: https://www.jobindex.dk/jobsoegning.rss?q={query}&superjob=1
    """

    def fetch(self, queries: list[str]) -> list[JobListing]:
        results = []
        base_url = self.config.get(
            "rss_url",
            "https://www.jobindex.dk/jobsoegning.rss?q={query}&superjob=1"
        )

        for query in queries:
            try:
                url = base_url.format(query=urllib.parse.quote(query))
                items = fetch_rss(url)
                listings = rss_to_listings(items, self.config)
                print(f"  [Jobindex] '{query}' → {len(listings)} jobs")
                results.extend(listings)
            except Exception as e:
                print(f"  [Jobindex] Error on query '{query}': {e}")

        return results
