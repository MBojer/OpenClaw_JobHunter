"""
scripts/db/reset_dev.py
DEV ONLY — wipes all data and starts a fresh agent session.
Clears: jobs, profile, profile_experience, applications, documents, spend_log, run_log, boards.
Preserves: schema, schema_migrations.
Then runs: openclaw sessions cleanup --enforce

Usage:
    python3 scripts/db/reset_dev.py [--yes]
"""
import sys
import subprocess
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from scripts.db.client import execute

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
CONFIG_FILES = ["profile.json", "preferences.json"]


def reset(confirmed: bool):
    if not confirmed:
        answer = input("⚠️  This will DELETE ALL DATA (jobs, profile, applications, spend_log, run_log).\nType YES to confirm: ")
        if answer.strip() != "YES":
            print("Aborted.")
            sys.exit(0)

    print("\nClearing database...")

    # Order matters — FK constraints
    execute("DELETE FROM documents")
    execute("DELETE FROM spend_log")
    execute("DELETE FROM applications")
    execute("DELETE FROM jobs")
    execute("DELETE FROM run_log")
    execute("DELETE FROM profile_experience")
    execute("DELETE FROM profile")
    execute("DELETE FROM boards")

    print("  ✓ All tables cleared")

    for fname in CONFIG_FILES:
        fpath = CONFIG_DIR / fname
        if fpath.exists():
            fpath.unlink()
            print(f"  ✓ Removed {fpath.name}")

    print("\nResetting agent session...")
    result = subprocess.run(
        ["openclaw", "sessions", "cleanup", "--enforce"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("  ✓ Session cleared")
    else:
        print(f"  ⚠ Session cleanup returned non-zero: {result.stderr.strip() or result.stdout.strip()}")

    print("\n✅ Reset complete. Open the onboarding form or send /onboard to start fresh.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DEV reset — wipes all data and session")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    reset(confirmed=args.yes)
