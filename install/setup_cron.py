"""
install/setup_cron.py
Registers JobHunter cron jobs using the OpenClaw CLI.
Cron jobs are stored in ~/.openclaw/cron/jobs.json — NOT in openclaw.json.
Also removes any stale 'cron' array previously written to openclaw.json.
"""
import argparse
import json
import subprocess
import sys
import os
from pathlib import Path

CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
WORKSPACE   = Path(os.environ.get(
    "OPENCLAW_WORKSPACE",
    Path.home() / ".openclaw" / "workspace-jobhunter"
))

parser = argparse.ArgumentParser()
parser.add_argument("--morning",    default="7:00")
parser.add_argument("--evening",    default="17:00")
parser.add_argument("--digest",     default="8:00")
parser.add_argument("--no-evening", action="store_true", dest="no_evening")
args, _ = parser.parse_known_args()


def _cron(hhmm: str) -> str:
    h, m = hhmm.split(":")
    return f"{int(m)} {int(h)} * * *"


CRON_JOBS = [
    {
        "id":       "jobhunter-morning-scrape",
        "cron":     _cron(args.morning),
        "message":  "SYSTEM: Run the job scrape now. Execute: python3 scripts/scraping/run_scrape.py",
        "desc":     f"JobHunter: morning scrape + score + dedup ({args.morning})",
    },
    *([] if args.no_evening else [{
        "id":       "jobhunter-evening-scrape",
        "cron":     _cron(args.evening),
        "message":  "SYSTEM: Run the job scrape now. Execute: python3 scripts/scraping/run_scrape.py",
        "desc":     f"JobHunter: evening scrape + score + dedup ({args.evening})",
    }]),
    {
        "id":       "jobhunter-digest",
        "cron":     _cron(args.digest),
        "message":  (
            "SYSTEM: Run the daily digest. "
            "Query top new jobs from the last 24 hours "
            "(status='new', not 'duplicate') ORDER BY score DESC LIMIT 10. "
            "Format and send the digest to the user."
        ),
        "desc":     f"JobHunter: daily digest to Telegram ({args.digest})",
    },
]


def clean_stale_cron_from_config():
    """Remove any 'cron' array previously written to openclaw.json by mistake."""
    if not CONFIG_PATH.exists():
        return
    try:
        config = json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError:
        return

    if isinstance(config.get("cron"), list):
        print("  Removing stale 'cron' array from openclaw.json...")
        del config["cron"]
        CONFIG_PATH.write_text(json.dumps(config, indent=2))
        print("  ✓ Cleaned openclaw.json")


def job_exists(job_id: str) -> bool:
    result = subprocess.run(
        ["openclaw", "cron", "list", "--json"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return False
    try:
        jobs = json.loads(result.stdout)
        return any(j.get("id") == job_id or j.get("name") == job_id
                   for j in (jobs if isinstance(jobs, list) else []))
    except Exception:
        return False


def remove_job(job_id: str):
    subprocess.run(
        ["openclaw", "cron", "rm", job_id, "--yes"],
        capture_output=True
    )


def add_job(job: dict):
    cmd = [
        "openclaw", "cron", "add",
        "--name",    job["id"],
        "--cron",    job["cron"],
        "--message", job["message"],
        "--agent",   "jobhunter",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ Failed: {result.stderr.strip() or result.stdout.strip()}")
        return False
    return True


if __name__ == "__main__":
    # Step 1: Remove bad cron array from openclaw.json if present
    clean_stale_cron_from_config()

    # Step 2: Register jobs via CLI
    print("Registering cron jobs via openclaw CLI...")
    ok = 0
    for job in CRON_JOBS:
        # Remove existing version for idempotency
        if job_exists(job["id"]):
            remove_job(job["id"])

        if add_job(job):
            print(f"  ✓ [{job['cron']}] {job['desc']}")
            ok += 1
        else:
            print(f"  ✗ Failed to register: {job['id']}")

    print(f"\n{ok}/{len(CRON_JOBS)} cron jobs registered.")
    print("Jobs stored in: ~/.openclaw/cron/jobs.json")

    if ok < len(CRON_JOBS):
        sys.exit(1)