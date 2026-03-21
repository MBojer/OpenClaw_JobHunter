# Adding a Job Board

Adding a new board takes about 15 minutes. Here's the full process.

---

## Step 1: Decide the tier

| Tier | Method | When to use |
|---|---|---|
| 1 | RSS/Atom feed | Board has a public RSS feed — always prefer this |
| 2 | HTML scraper | No RSS; use stdlib `urllib` + `re`, no heavy deps |
| 3 | Manual paste | Anti-scraping too aggressive (e.g. LinkedIn) |

Check if the board has RSS first. Most Danish job boards do.
Try: `https://www.boardname.dk/jobsoegning.rss?q=developer`

---

## Step 2: Copy the template

```bash
cp scripts/scraping/boards/_template.py scripts/scraping/boards/myboard.py
```

---

## Step 3: Implement the connector

Open `scripts/scraping/boards/myboard.py` and implement `fetch()`.

### Tier 1 (RSS) example:
```python
from scripts.scraping.rss_connector import fetch_rss, rss_to_listings

def fetch(self, queries: list[str]) -> list[JobListing]:
    results = []
    for query in queries:
        try:
            url = self.config["rss_url"].format(query=urllib.parse.quote(query))
            items = fetch_rss(url)
            results.extend(rss_to_listings(items, self.config))
        except Exception as e:
            print(f"  [{self.name()}] Error: {e}")
    return results
```

### Tier 2 (HTML) example:
```python
import urllib.request, re, html

def fetch(self, queries: list[str]) -> list[JobListing]:
    results = []
    for query in queries:
        try:
            url = f"{self.config['base_url']}?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                page = r.read().decode("utf-8", errors="replace")
            results.extend(self._parse(page))
        except Exception as e:
            print(f"  [{self.name()}] Error: {e}")
    return results
```

**Rules for HTML scrapers:**
- Use only stdlib (`urllib`, `re`, `html`) — no BeautifulSoup, no requests
- Catch all exceptions inside `fetch()` — never let a broken scraper crash the whole run
- Target only `url`, `title`, `company` from HTML — description is optional at scrape time

---

## Step 4: Register in `CONNECTOR_MAP`

Open `scripts/scraping/run_scrape.py` and add your board:

```python
CONNECTOR_MAP = {
    "jobindex":   "scripts.scraping.boards.jobindex.JobindexConnector",
    "indeed":     "scripts.scraping.boards.indeed.IndeedConnector",
    "it_jobbank": "scripts.scraping.boards.it_jobbank.ItJobbankConnector",
    "myboard":    "scripts.scraping.boards.myboard.MyBoardConnector",  # ← add this
}
```

---

## Step 5: Register in `board_registry.json`

Open `skills/job-scraper/board_registry.json` and add:

```json
{
  "slug": "myboard",
  "name": "My Board",
  "tier": 1,
  "enabled": true,
  "connector": "scripts/scraping/boards/myboard.py",
  "rss_url": "https://myboard.dk/rss?q={query}",
  "queries": []
}
```

Leave `queries` as `[]` — search queries come from the user's preferences.

---

## Step 6: Test it

```bash
# Dry run — no DB writes
python scripts/scraping/run_scrape.py --board myboard --dry-run

# Real run — saves to DB
python scripts/scraping/run_scrape.py --board myboard
```

---

## Step 7: Commit

```bash
git add scripts/scraping/boards/myboard.py
git add scripts/scraping/run_scrape.py
git add skills/job-scraper/board_registry.json
git commit -m "feat: add myboard connector (tier 1, RSS)"
git push
```

The running agent picks up the new board on the next cron scrape — no restart needed.
