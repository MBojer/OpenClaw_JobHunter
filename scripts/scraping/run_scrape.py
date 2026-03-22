"""
scripts/scraping/run_scrape.py
Entry point for all scraping runs.
Reads board_registry.json, runs all enabled boards, deduplicates, stores results.
Automatically triggers score_jobs.py after a successful scrape.
"""
import sys
import json
import argparse
import hashlib
import importlib
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.db.client import fetchone, fetchall, execute
from scripts.scraping.base_connector import JobListing

REGISTRY_PATH = (
    Path(__file__).parent.parent.parent
    / "skills" / "job-scraper" / "board_registry.json"
)

CONNECTOR_MAP = {
    "jobindex":   "scripts.scraping.boards.jobindex.JobindexConnector",
    "searxng":    "scripts.scraping.boards.searxng.SearxngConnector",
    "indeed":     "scripts.scraping.boards.indeed.IndeedConnector",
    "it_jobbank": "scripts.scraping.boards.it_jobbank.ItJobbankConnector",
}


def load_connector(slug: str, config: dict):
    class_path = CONNECTOR_MAP.get(slug)
    if not class_path:
        raise ValueError(f"No connector registered for board slug: {slug}")
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)(config)


def load_queries() -> list[str]:
    """Read search queries from user preferences."""
    row = fetchone("SELECT preferences FROM profile WHERE id = 1")
    if not row or not row["preferences"]:
        return []
    prefs = row["preferences"]
    return prefs.get("job_titles", [])


def url_exists(url: str) -> bool:
    row = fetchone("SELECT 1 FROM jobs WHERE url = %s", (url,))
    return row is not None


def save_job(listing: JobListing, board_id: int) -> bool:
    """Insert job. Returns True if new, False if duplicate."""
    if url_exists(listing.url):
        return False
    execute("""
        INSERT INTO jobs
            (board_id, url, title, company, location, remote,
             description_raw, scraped_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (url) DO NOTHING
    """, (
        board_id,
        listing.url,
        listing.title[:256],
        listing.company[:256] if listing.company else None,
        listing.location[:256] if listing.location else None,
        listing.remote,
        listing.description_raw,
        listing.scraped_at,
    ))
    return True


def run(board_filter: str = None, dry_run: bool = False):
    registry = json.loads(REGISTRY_PATH.read_text())
    queries  = load_queries()

    if not queries:
        print("⚠️  No job titles in preferences. Run onboarding first.")
        print("   Defaulting to empty query (board default results).")
        queries = [""]

    boards = [b for b in registry["boards"] if b["enabled"]]
    if board_filter:
        boards = [b for b in boards if b["slug"] == board_filter]

    if not boards:
        print("No enabled boards found.")
        return

    total_new   = 0
    total_found = 0
    run_status  = "ok"

    for board in boards:
        slug = board["slug"]
        print(f"\n[{board['name']}] Starting scrape...")

        # Ensure board row exists in DB
        db_board = fetchone("SELECT id FROM boards WHERE slug = %s", (slug,))
        if not db_board:
            execute("""
                INSERT INTO boards (slug, name, tier, enabled, config)
                VALUES (%s, %s, %s, TRUE, %s)
            """, (slug, board["name"], board["tier"], json.dumps(board)))
            db_board = fetchone("SELECT id FROM boards WHERE slug = %s", (slug,))
        board_id = db_board["id"]

        try:
            connector = load_connector(slug, board)
            listings  = connector.fetch(queries)
            total_found += len(listings)

            new_count = 0
            for listing in listings:
                if dry_run:
                    print(f"  [DRY RUN] {listing.title} @ {listing.company} — {listing.url}")
                    new_count += 1
                else:
                    if save_job(listing, board_id):
                        new_count += 1

            total_new += new_count
            print(f"  → {len(listings)} fetched, {new_count} new")

            if not dry_run:
                execute(
                    "UPDATE boards SET last_run_at = NOW() WHERE id = %s",
                    (board_id,)
                )
                execute("""
                    INSERT INTO run_log
                        (run_type, board_slug, status, jobs_found, jobs_new, finished_at)
                    VALUES ('scrape', %s, 'ok', %s, %s, NOW())
                """, (slug, len(listings), new_count))

        except Exception as e:
            run_status = "partial"
            print(f"  ✗ Error scraping {slug}: {e}")
            if not dry_run:
                execute("""
                    INSERT INTO run_log
                        (run_type, board_slug, status, error_msg, finished_at)
                    VALUES ('scrape', %s, 'error', %s, NOW())
                """, (slug, str(e)[:500]))

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Scrape complete: "
          f"{total_found} found, {total_new} new jobs saved.")

    # Trigger scoring automatically unless dry-run
    if not dry_run and total_new > 0:
        print("\nTriggering scoring...")
        import subprocess
        subprocess.run(
            [sys.executable, "scripts/local_llm/score_jobs.py"],
            check=False
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--board",   type=str, help="Scrape a single board by slug")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(board_filter=args.board, dry_run=args.dry_run)