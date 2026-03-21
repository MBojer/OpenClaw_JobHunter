"""
scripts/scraping/boards/_template.py

COPY THIS FILE to create a new board connector.
Rename it to your board's slug, e.g. `myjobboard.py`

Steps:
  1. Copy this file: cp _template.py myboard.py
  2. Fill in the class below
  3. Add an entry to skills/job-scraper/board_registry.json
  4. Test: python scripts/scraping/run_scrape.py --board myboard --dry-run

See docs/adding-a-board.md for full instructions.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.scraping.base_connector import BaseConnector, JobListing


class MyBoardConnector(BaseConnector):
    """
    Connector for MyBoard.com
    Tier: 1 (RSS) or 2 (HTML scraper)
    """

    def fetch(self, queries: list[str]) -> list[JobListing]:
        """
        Fetch jobs for each query string.
        Return a flat list of JobListing objects.
        Never raise — catch exceptions and return partial results.
        """
        results = []

        for query in queries:
            try:
                # --- Tier 1 example (RSS) ---
                # from scripts.scraping.rss_connector import fetch_rss, rss_to_listings
                # url = self.config["rss_url"].format(query=query)
                # items = fetch_rss(url)
                # results.extend(rss_to_listings(items, self.config))

                # --- Tier 2 example (HTML) ---
                # import urllib.request
                # url = f"{self.config['base_url']}?q={query}"
                # with urllib.request.urlopen(url) as r:
                #     html = r.read().decode()
                # results.extend(self._parse_html(html))

                pass  # Remove this once implemented

            except Exception as e:
                print(f"  [{self.name()}] Error on query '{query}': {e}")

        return results

    # def _parse_html(self, html: str) -> list[JobListing]:
    #     """HTML-specific parsing logic."""
    #     listings = []
    #     # Parse with html.parser or similar — no heavy deps
    #     return listings
