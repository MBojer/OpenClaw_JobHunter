#!/usr/bin/env python3
"""
scripts/onboarding/stop_server.py
Stop the background onboarding web server and remove the agent lock file.

Usage:
    python3 scripts/onboarding/stop_server.py
"""
import json
import os
import signal
import sys
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent.parent
PID_FILE  = WORKSPACE / "tmp" / "onboarding_server.pid"
LOCK_FILE = WORKSPACE / "tmp" / "onboarding_active"


def main():
    stopped = False
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            stopped = True
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        PID_FILE.unlink(missing_ok=True)

    LOCK_FILE.unlink(missing_ok=True)
    print(json.dumps({"stopped": stopped}))


if __name__ == "__main__":
    main()
