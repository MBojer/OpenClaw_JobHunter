"""
scripts/onboarding/web_server.py
Lightweight Flask server for the web-based onboarding form.
Runs on port 8080 by default (configurable via ONBOARDING_PORT env var).

Usage:
    python3 scripts/onboarding/web_server.py [--port PORT]
"""
import sys
import json
import os
import signal
import subprocess
import threading
import argparse
import secrets
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_file, session, redirect, url_for, Response
from scripts.local_llm.ollama_client import generate, is_available
from scripts.db.client import fetchone
from scripts.onboarding.parse_profile import save_profile, parse_raw

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

WORKSPACE         = Path(__file__).parent.parent.parent
FORM_PATH         = Path(__file__).parent / "onboarding_form.html"
BOARDS_FORM_PATH  = Path(__file__).parent / "boards_form.html"
AGENT_SETUP_PATH  = Path(__file__).parent / "agent_setup.html"
BOARD_REGISTRY_PATH = WORKSPACE / "skills" / "job-scraper" / "board_registry.json"
VALIDATE_PROMPT_PATH = WORKSPACE / "skills" / "onboarding" / "validate_prompt.txt"
PIN_FILE          = WORKSPACE / "tmp" / "onboarding_pin"


# ─── PIN auth ─────────────────────────────────────────────────────────────────

_PIN_FORM = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JobHunter — Enter PIN</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,-apple-system,sans-serif;background:#0f0f1a;color:#e2e2f0;
     display:flex;align-items:center;justify-content:center;min-height:100vh}}
.box{{background:#1a1a2e;border-radius:12px;padding:2.5rem;width:320px;
      box-shadow:0 4px 24px rgba(0,0,0,.4);text-align:center}}
h1{{font-size:1.2rem;font-weight:600;margin-bottom:.4rem}}
p{{font-size:.85rem;color:#9090b0;margin-bottom:1.75rem}}
input{{width:100%;padding:.65rem .9rem;border:1px solid #2e2e4a;border-radius:8px;
       background:#0d0d1c;color:#e2e2f0;font-size:1.6rem;text-align:center;
       letter-spacing:.4em;margin-bottom:1rem;box-sizing:border-box;font-family:monospace}}
input:focus{{outline:none;border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.2)}}
button{{width:100%;background:#6366f1;color:#fff;border:none;border-radius:8px;
        padding:.75rem;font-size:1rem;cursor:pointer;font-family:inherit;font-weight:500}}
button:hover{{background:#818cf8}}
.err{{color:#fca5a5;font-size:.85rem;margin-top:.9rem}}
</style>
</head>
<body>
<div class="box">
  <h1>🦞 JobHunter</h1>
  <p>Enter the PIN sent to your Telegram</p>
  <form method="POST" action="/onboard/auth">
    <input type="text" name="pin" maxlength="6" inputmode="numeric"
           autocomplete="off" autofocus placeholder="000000">
    <button type="submit">Unlock</button>
    {error}
  </form>
</div>
</body>
</html>"""


def _read_pin() -> str | None:
    try:
        return PIN_FILE.read_text().strip()
    except FileNotFoundError:
        return None


@app.before_request
def require_pin():
    if request.path in ("/onboard/auth",):
        return None
    if not session.get("authed"):
        return Response(_PIN_FORM.format(error=""), content_type="text/html")


@app.route("/onboard/auth", methods=["POST"])
def auth_pin():
    entered = (request.form.get("pin") or "").strip()
    correct = _read_pin()
    if correct and entered == correct:
        session["authed"] = True
        return redirect(url_for("onboard"))
    err = '<p class="err">Incorrect PIN — try again</p>'
    return Response(_PIN_FORM.format(error=err), content_type="text/html"), 401


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("onboard"))


@app.route("/onboard", strict_slashes=False)
def onboard():
    return send_file(FORM_PATH)


@app.route("/onboard/boards")
def onboard_boards():
    return send_file(BOARDS_FORM_PATH)


@app.route("/onboard/agent-setup")
def agent_setup():
    return send_file(AGENT_SETUP_PATH)


# ─── Profile API ──────────────────────────────────────────────────────────────

def _load_validate_prompt() -> str:
    return VALIDATE_PROMPT_PATH.read_text(encoding="utf-8")


@app.route("/onboard/status")
def status():
    row = fetchone("SELECT structured, preferences FROM profile WHERE id = 1")
    if not row or not row.get("structured"):
        return jsonify({"onboarded": False})
    return jsonify({
        "onboarded": True,
        "profile": row["structured"] or {},
        "preferences": row["preferences"] or {},
    })


def _extract_text_pdf(data: bytes) -> str:
    import pdfplumber, io
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _extract_text_docx(data: bytes) -> str:
    import docx, io
    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)


@app.route("/onboard/import", methods=["POST"])
def import_cv():
    if not is_available():
        return jsonify({"error": "Ollama is not reachable — is it running?"}), 503

    raw_text = ""

    if request.files.get("file"):
        f = request.files["file"]
        data = f.read()
        fname = (f.filename or "").lower()
        try:
            if fname.endswith(".pdf"):
                raw_text = _extract_text_pdf(data)
            elif fname.endswith(".docx"):
                raw_text = _extract_text_docx(data)
            else:
                return jsonify({"error": "Unsupported file type — use PDF or DOCX"}), 400
        except Exception as e:
            return jsonify({"error": f"Could not read file: {e}"}), 400
    else:
        body = request.get_json(silent=True) or {}
        raw_text = body.get("text", "").strip()

    if not raw_text:
        return jsonify({"error": "No text could be extracted"}), 400

    try:
        profile = parse_raw(raw_text)
        suggested_titles = profile.pop("suggested_job_titles", [])
        return jsonify({"profile": profile, "suggested_titles": suggested_titles})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/onboard/validate", methods=["POST"])
def validate():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    if not is_available():
        return jsonify({"error": "Ollama is not reachable — is it running?"}), 503

    prompt = _load_validate_prompt() + "\n" + json.dumps(data, indent=2, ensure_ascii=False)

    try:
        response = generate(prompt, temperature=0.1, json_mode=True, num_predict=2048)
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])
        result = json.loads(response)
        result.setdefault("issues", [])
        return jsonify(result)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Qwen returned invalid JSON: {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/onboard/save", methods=["POST"])
def save():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    profile = data.get("profile", {})
    preferences = data.get("preferences", {})

    try:
        save_profile(profile, preferences)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Boards API ───────────────────────────────────────────────────────────────

@app.route("/onboard/boards/status")
def boards_status():
    registry = json.loads(BOARD_REGISTRY_PATH.read_text(encoding="utf-8"))
    visible_boards = [
        {"slug": b["slug"], "name": b["name"], "tier": b["tier"], "enabled": b["enabled"]}
        for b in registry["boards"]
        if not b.get("ui_hidden")
    ]
    searxng_entry = next((b for b in registry["boards"] if b["slug"] == "searxng"), {})
    searxng_config = {
        "engines": searxng_entry.get("engines", ""),
        "time_range": searxng_entry.get("time_range", "month"),
        "language": searxng_entry.get("language", ""),
    }
    row = fetchone("SELECT preferences FROM profile WHERE id = 1")
    prefs = (row.get("preferences") or {}) if row else {}
    job_boards = prefs.get("job_boards", [])
    return jsonify({"boards": visible_boards, "job_boards": job_boards, "searxng": searxng_config})


@app.route("/onboard/boards/save", methods=["POST"])
def boards_save():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    registry = json.loads(BOARD_REGISTRY_PATH.read_text(encoding="utf-8"))
    board_enabled = data.get("boards", {})
    searxng_update = data.get("searxng", {})

    for b in registry["boards"]:
        if b.get("ui_hidden"):
            continue
        if b["slug"] in board_enabled:
            b["enabled"] = bool(board_enabled[b["slug"]])
        if b["slug"] == "searxng":
            for key in ("engines", "time_range", "language"):
                if key in searxng_update:
                    b[key] = searxng_update[key]

    BOARD_REGISTRY_PATH.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    row = fetchone("SELECT preferences FROM profile WHERE id = 1")
    if row:
        prefs = row.get("preferences") or {}
        prefs["job_boards"] = data.get("job_boards", [])
        from scripts.db.client import execute
        execute("UPDATE profile SET preferences=%s WHERE id=1", [json.dumps(prefs)])

    return jsonify({"ok": True})


# ─── Agent setup API ──────────────────────────────────────────────────────────

@app.route("/onboard/agent-setup/run", methods=["POST"])
def agent_setup_run():
    data = request.get_json(silent=True) or {}
    cmd = [
        sys.executable, str(WORKSPACE / "install" / "setup_cron.py"),
        "--morning", data.get("morning", "7:00"),
        "--evening", data.get("evening", "17:00"),
        "--digest",  data.get("digest",  "8:00"),
    ]
    if not data.get("evening_enabled", True):
        cmd.append("--no-evening")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        return jsonify({"ok": True, "output": result.stdout})
    return jsonify({"ok": False, "error": result.stderr or result.stdout}), 500


@app.route("/onboard/agent-setup/done", methods=["POST"])
def agent_setup_done():
    lock = WORKSPACE / "tmp" / "onboarding_active"
    lock.unlink(missing_ok=True)

    def _shutdown():
        import time
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=_shutdown, daemon=True).start()
    return jsonify({"ok": True})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JobHunter onboarding web server")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ONBOARDING_PORT", 8080)),
        help="Port to listen on (default: 8080)",
    )
    args = parser.parse_args()
    print(f"🦞 JobHunter Onboarding — http://0.0.0.0:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)
