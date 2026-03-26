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
import argparse
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_file
from scripts.local_llm.ollama_client import generate, is_available
from scripts.db.client import fetchone
from scripts.onboarding.parse_profile import save_profile, parse_raw

app = Flask(__name__)

FORM_PATH = Path(__file__).parent / "onboarding_form.html"
VALIDATE_PROMPT_PATH = (
    Path(__file__).parent.parent.parent / "skills" / "onboarding" / "validate_prompt.txt"
)


def _load_validate_prompt() -> str:
    return VALIDATE_PROMPT_PATH.read_text(encoding="utf-8")


@app.route("/")
def index():
    return send_file(FORM_PATH)


@app.route("/status")
def status():
    """Return current profile for prepopulating the form, or onboarded=False."""
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


@app.route("/import", methods=["POST"])
def import_cv():
    """Parse a CV file (PDF/DOCX) or pasted text via Qwen. Returns structured profile JSON."""
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
        return jsonify({"profile": profile})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/validate", methods=["POST"])
def validate():
    """Send form data to Qwen for cleaning + validation. Returns cleaned JSON + issues list."""
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
        # Ensure issues key always exists
        result.setdefault("issues", [])
        return jsonify(result)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Qwen returned invalid JSON: {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/save", methods=["POST"])
def save():
    """Save the (already validated) profile + preferences to DB and config files."""
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
