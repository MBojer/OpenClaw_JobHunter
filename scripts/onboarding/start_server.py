#!/usr/bin/env python3
"""
scripts/onboarding/start_server.py
Start the onboarding web server in the background and print the public URL.
Creates tmp/onboarding_active to block the agent while the form is open.

Usage:
    python3 scripts/onboarding/start_server.py [--port PORT]
"""
import json
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dotenv import load_dotenv
load_dotenv()

WORKSPACE = Path(__file__).parent.parent.parent
PID_FILE  = WORKSPACE / "tmp" / "onboarding_server.pid"
LOCK_FILE = WORKSPACE / "tmp" / "onboarding_active"
PORT      = int(os.environ.get("ONBOARDING_PORT", 8080))
BASE_URL  = os.environ.get("OPENCLAW_BASE_URL", "").rstrip("/")


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _existing_pid() -> int | None:
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except ValueError:
            pass
    return None


def main():
    (WORKSPACE / "tmp").mkdir(exist_ok=True)

    existing = _existing_pid()
    already  = existing and _pid_alive(existing) and _port_in_use(PORT)

    if not already:
        server = Path(__file__).parent / "web_server.py"
        proc   = subprocess.Popen(
            [sys.executable, str(server), "--port", str(PORT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        PID_FILE.write_text(str(proc.pid))

    LOCK_FILE.write_text("onboarding_in_progress")

    url = f"{BASE_URL}/onboard" if BASE_URL else f"http://localhost:{PORT}"
    print(json.dumps({"url": url, "port": PORT, "already_running": bool(already)}))


if __name__ == "__main__":
    main()
