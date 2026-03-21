"""
install/setup_cron.py
Registers JobHunter cron jobs in ~/.openclaw/openclaw.json.
The repo IS the workspace, so script paths resolve from there.
Safe to re-run — will not duplicate jobs.
"""
import json
import sys
import os
from pathlib import Path

CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
WORKSPACE   = Path(os.environ.get(
    "OPENCLAW_WORKSPACE",
    Path.home() / ".openclaw" / "workspace-jobhunter"
))

# Scripts live inside the workspace (repo root)
SCRAPE_CMD = f"python {WORKSPACE}/scripts/scraping/run_scrape.py"

CRON_JOBS = [
    {
        "id":          "jobhunter-morning-scrape",
        "schedule":    "0 7 * * *",
        "command":     SCRAPE_CMD,
        "description": "JobHunter: morning scrape + score + dedup",
        "agentId":     "jobhunter",
    },
    {
        "id":          "jobhunter-evening-scrape",
        "schedule":    "0 17 * * *",
        "command":     SCRAPE_CMD,
        "description": "JobHunter: evening scrape + score + dedup",
        "agentId":     "jobhunter",
    },
    {
        "id":          "jobhunter-digest",
        "schedule":    "0 8 * * *",
        "message":     (
            "SYSTEM: Run the daily digest. "
            "Query top new jobs from the last 24 hours "
            "(status='new', not 'duplicate', score >= min_score) "
            "ORDER BY score DESC LIMIT 10. "
            "Format and send the digest to the user."
        ),
        "description": "JobHunter: daily digest to Telegram",
        "agentId":     "jobhunter",
    },
]


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_config(config: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def register_cron(config: dict) -> dict:
    existing  = config.get("cron", [])
    jh_ids    = {j["id"] for j in CRON_JOBS}
    cleaned   = [j for j in existing if j.get("id") not in jh_ids]
    config["cron"] = cleaned + CRON_JOBS
    return config


if __name__ == "__main__":
    config  = load_config()
    updated = register_cron(config)
    save_config(updated)

    print("Cron jobs registered:")
    for job in CRON_JOBS:
        print(f"  [{job['schedule']}] {job['description']}")
    print(f"\nConfig saved to {CONFIG_PATH}")
    print(f"Script path base: {WORKSPACE}")
