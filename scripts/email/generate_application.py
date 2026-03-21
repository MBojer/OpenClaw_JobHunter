"""
scripts/email/generate_application.py
Generate CV and cover letter for a job using Together.ai.
- Checks budget before spending
- Cleans tmp/ at start
- Stores binary documents in DB (safe from reinstalls)
- Logs every API call to spend_log
- NEVER applies on behalf of the user
- NEVER sends emails — call deliver_documents.py after user confirms
"""
import os
import sys
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.db.client import fetchone, execute
from scripts.db.check_budget import check as check_budget
from dotenv import load_dotenv

load_dotenv()

TOGETHER_API_KEY = os.environ["TOGETHER_API_KEY"]
TOGETHER_MODEL   = os.environ.get(
    "TOGETHER_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo"
)

WORKSPACE = Path(os.environ.get(
    "OPENCLAW_WORKSPACE",
    Path.home() / ".openclaw" / "workspace-jobhunter"
))
TMP_DIR = WORKSPACE / "tmp"

WRITER_PROMPT = (
    Path(__file__).parent.parent.parent / "skills" / "cv-writer" / "writer-agent.md"
).read_text()


def clean_tmp():
    """Remove all files in tmp/ before generating new ones."""
    if TMP_DIR.exists():
        for f in TMP_DIR.iterdir():
            if f.is_file():
                f.unlink()
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def compute_input_hash(job_id: str, profile_hash: str) -> str:
    return hashlib.sha256(f"{job_id}|{profile_hash}".encode()).hexdigest()


def get_profile_hash() -> str:
    row = fetchone("SELECT profile_hash FROM profile WHERE id = 1")
    return row["profile_hash"] if row and row["profile_hash"] else "no_profile"


def call_together(prompt: str) -> tuple[str, int, int]:
    """Call Together.ai. Returns (text, prompt_tokens, completion_tokens)."""
    import urllib.request, urllib.error

    payload = json.dumps({
        "model":       TOGETHER_MODEL,
        "messages":    [{"role": "user", "content": prompt}],
        "max_tokens":  4000,
        "temperature": 0.4,
    }).encode()

    req = urllib.request.Request(
        "https://api.together.xyz/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {TOGETHER_API_KEY}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())

    text              = data["choices"][0]["message"]["content"]
    prompt_tokens     = data.get("usage", {}).get("prompt_tokens", 0)
    completion_tokens = data.get("usage", {}).get("completion_tokens", 0)
    return text, prompt_tokens, completion_tokens


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens + completion_tokens) / 1_000_000 * 0.90


def store_document(app_id: str, job_id: str, doc_type: str,
                   path: Path) -> str:
    """Store a file in the documents table. Returns document UUID."""
    content = path.read_bytes()
    content_hash = hashlib.sha256(content).hexdigest()

    row = execute("""
        INSERT INTO documents
            (application_id, job_id, doc_type, filename,
             content, content_hash, size_bytes)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (app_id, job_id, doc_type, path.name,
          content, content_hash, len(content)))
    return row  # rowcount only — UUID fetched separately if needed


def write_placeholder_docs(job_id: str, cv_text: str, cl_text: str) -> dict[str, Path]:
    """
    Write markdown files to tmp/.
    v2.0: Markdown only — docx/pdf generation is v2.1.
    Returns dict of doc_type -> Path.
    """
    files = {
        "cv_docx":  TMP_DIR / f"cv_{job_id}.md",   # placeholder extension until docx generation
        "cl_docx":  TMP_DIR / f"cl_{job_id}_cover.md",
    }
    files["cv_docx"].write_text(cv_text)
    files["cl_docx"].write_text(cl_text)

    # TODO v2.1: convert markdown → docx using python-docx
    # TODO v2.1: convert docx → pdf using libreoffice headless or weasyprint
    # For now, md files serve as the deliverable

    return files


def generate(job_id: str):
    # ── Budget check (direct function call — no subprocess) ────────────────
    budget = check_budget()
    if budget["refuse"]:
        print(f"⛔ Budget exhausted (${budget['remaining_usd']:.2f} left).")
        sys.exit(2)
    if budget["warn"]:
        print(f"⚠️  Budget low: ${budget['remaining_usd']:.2f} remaining.")

    # ── Check for existing application (dedup by input_hash) ───────────────
    profile_hash = get_profile_hash()
    input_hash   = compute_input_hash(job_id, profile_hash)

    existing = fetchone("""
        SELECT id, generated_at FROM applications WHERE input_hash = %s
    """, (input_hash,))
    if existing:
        print(f"⚠️  Documents already generated for this job with your current profile.")
        print(f"   Generated at: {existing['generated_at']}")
        print(f"   Use --force to regenerate, or run deliver_documents.py to redeliver.")
        sys.exit(0)

    # ── Load data ──────────────────────────────────────────────────────────
    job = fetchone("""
        SELECT id, title, company, location, description_raw, url
        FROM jobs WHERE id = %s
    """, (job_id,))
    if not job:
        print(f"ERROR: Job {job_id} not found.")
        sys.exit(1)

    profile_path = Path(__file__).parent.parent.parent / "config" / "profile.json"
    if not profile_path.exists():
        print("ERROR: config/profile.json not found. Run onboarding first.")
        sys.exit(1)
    profile    = json.loads(profile_path.read_text())
    cv_base    = (Path(__file__).parent.parent.parent
                  / "skills" / "cv-writer" / "cv_base.md").read_text()

    # ── Build prompt ───────────────────────────────────────────────────────
    prompt = (
        f"{WRITER_PROMPT}\n\n"
        f"## Candidate Profile\n{json.dumps(profile, indent=2)}\n\n"
        f"## Job Posting\n"
        f"Title: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
        f"URL: {job['url']}\n\n"
        f"Description:\n{job['description_raw'][:4000]}\n\n"
        f"## Base CV Structure\n{cv_base}\n"
    )

    print(f"Generating CV + cover letter for: {job['title']} @ {job['company']}")

    # ── Clean tmp/ before generating ──────────────────────────────────────
    clean_tmp()

    # ── Call Together.ai ───────────────────────────────────────────────────
    text, p_tokens, c_tokens = call_together(prompt)
    cost = estimate_cost(p_tokens, c_tokens)

    # ── Parse output ───────────────────────────────────────────────────────
    if "=== CV ===" in text and "=== COVER LETTER ===" in text:
        parts  = text.split("=== COVER LETTER ===")
        cv_text = parts[0].replace("=== CV ===", "").strip()
        cl_text = parts[1].strip()
    else:
        cv_text = text
        cl_text = ""

    # ── Write tmp files ────────────────────────────────────────────────────
    files = write_placeholder_docs(job_id, cv_text, cl_text)

    # ── Create application record ──────────────────────────────────────────
    app_row = fetchone("""
        INSERT INTO applications
            (job_id, profile_hash, input_hash, status, generated_at)
        VALUES (%s, %s, %s, 'generated', NOW())
        RETURNING id
    """, (job_id, profile_hash, input_hash))
    app_id = str(app_row["id"])

    # ── Store documents in DB ─────────────────────────────────────────────
    for doc_type, path in files.items():
        store_document(app_id, job_id, doc_type, path)
        print(f"  ✓ Stored {doc_type} in database ({path.stat().st_size} bytes)")

    # ── Log spend ──────────────────────────────────────────────────────────
    execute("""
        INSERT INTO spend_log
            (provider, model, purpose, job_id,
             prompt_tokens, completion_tokens, estimated_usd)
        VALUES ('together', %s, 'cv_and_cover', %s, %s, %s, %s)
    """, (TOGETHER_MODEL, job_id, p_tokens, c_tokens, cost))

    # ── Update job status ──────────────────────────────────────────────────
    execute("UPDATE jobs SET status = 'applied', updated_at = NOW() WHERE id = %s",
            (job_id,))

    # ── Preview (cover letter only, 3 lines max) ───────────────────────────
    preview = [l for l in cl_text.split("\n") if l.strip()][:3]
    print(f"\n── Cover letter preview ──")
    print("\n".join(preview) if preview else "(No cover letter generated)")
    print("──────────────────────────")
    print(f"\n✓ Cost: ${cost:.4f} | Remaining budget: ${budget['remaining_usd'] - cost:.2f}")
    print(f"\nDocuments stored in database and ready in tmp/")
    print(f"Reply YES to deliver, EDIT to revise, CANCEL to abort.")
    print(f"\nNOTE: Delivery sends files to YOU only. The agent does not apply on your behalf.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--force",  action="store_true",
                        help="Regenerate even if documents already exist")
    args = parser.parse_args()
    generate(args.job_id)
