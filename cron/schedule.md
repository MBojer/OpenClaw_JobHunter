# Cron Schedule

Cron jobs are registered in OpenClaw config by the installer.

## Jobs

### 1. Morning scrape + score + dedup
- **When:** Every day at 07:00
- **Command:** `python /path/to/scripts/scraping/run_scrape.py`
- **Notes:** Automatically triggers `score_jobs.py` (scoring + dedup) after scraping

### 2. Evening scrape + score + dedup
- **When:** Every day at 17:00
- **Command:** `python /path/to/scripts/scraping/run_scrape.py`
- **Notes:** Catches jobs posted during business hours

### 3. Morning digest
- **When:** Every day at 08:00 (after morning scrape completes)
- **Notes:** Orchestrator reads DB and formats digest. Duplicates are excluded.
  The cron message to the agent:
  ```
  SYSTEM: Run the daily digest. Query top new jobs since yesterday
  (status='new', not 'duplicate') and send the digest to the user.
  ```

## OpenClaw cron config
Registered automatically by `install/setup_cron.py`.

```json
"cron": [
  {
    "id": "jobhunter-morning-scrape",
    "schedule": "0 7 * * *",
    "command": "python {{ install_dir }}/scripts/scraping/run_scrape.py",
    "description": "JobHunter: morning scrape + score + dedup"
  },
  {
    "id": "jobhunter-evening-scrape",
    "schedule": "0 17 * * *",
    "command": "python {{ install_dir }}/scripts/scraping/run_scrape.py",
    "description": "JobHunter: evening scrape + score + dedup"
  },
  {
    "id": "jobhunter-digest",
    "schedule": "0 8 * * *",
    "message": "SYSTEM: Run the daily digest. Query top new jobs from the last 24 hours (status='new', not 'duplicate') and send to the user.",
    "description": "JobHunter: daily digest to Telegram"
  }
]
```

## Notes
- Scrape at 07:00, digest at 08:00 — scoring and dedup run between them automatically
- No email polling — the mailbox is send-only for document delivery
- To trigger manually: `/scrape` or `/digest` in Telegram
- To redeliver existing documents: `/redeliver [N]`
