"""
scripts/email/deliver_documents.py
Deliver generated CV and cover letter documents to the user.

Delivery methods (configured in preferences.json):
  - "telegram": send files via OpenClaw Telegram channel
  - "email":    send files to PERSONAL_EMAIL via SMTP
  - "both":     deliver via both channels

SECURITY: The email recipient is always PERSONAL_EMAIL from .env.
          This script accepts no --to or recipient arguments.
          The agent calls: python scripts/email/deliver_documents.py --job-id <uuid>
          That is the full interface.
"""
import os
import sys
import json
import argparse
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.db.client import fetchone, fetchall, execute
from dotenv import load_dotenv

load_dotenv()

PERSONAL_EMAIL = os.environ.get("PERSONAL_EMAIL", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_USER_ID   = os.environ.get("TELEGRAM_USER_ID", "")

WORKSPACE = Path(os.environ.get(
    "OPENCLAW_WORKSPACE",
    Path.home() / ".openclaw" / "workspace-jobhunter"
))
TMP_DIR = WORKSPACE / "tmp"


def load_delivery_method() -> str:
    prefs_path = Path(__file__).parent.parent.parent / "config" / "preferences.json"
    if prefs_path.exists():
        prefs = json.loads(prefs_path.read_text())
        return prefs.get("delivery", {}).get("method", "telegram")
    return "telegram"


def get_tmp_files(job_id: str) -> dict[str, Path]:
    """Return expected tmp file paths for a job."""
    return {
        "cv_docx": TMP_DIR / f"cv_{job_id}.docx",
        "cv_pdf":  TMP_DIR / f"cv_{job_id}.pdf",
        "cl_docx": TMP_DIR / f"cl_{job_id}.docx",
        "cl_pdf":  TMP_DIR / f"cl_{job_id}.pdf",
    }


def restore_from_db(job_id: str) -> bool:
    """
    If tmp files are missing, restore from documents table.
    Returns True if all 4 files are now present.
    """
    docs = fetchall("""
        SELECT doc_type, filename, content
        FROM documents WHERE job_id = %s
    """, (job_id,))

    if not docs:
        return False

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    paths = get_tmp_files(job_id)

    for doc in docs:
        path = paths.get(doc["doc_type"])
        if path:
            path.write_bytes(bytes(doc["content"]))
            print(f"  Restored {doc['doc_type']} from database")

    return all(p.exists() for p in paths.values())


def deliver_via_telegram(job: dict, files: dict[str, Path]):
    """Send document files as Telegram attachments via Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_USER_ID:
        print("  ✗ Telegram not configured — skipping Telegram delivery")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"

    # Send a message first
    caption = (
        f"📄 Documents ready for: {job['title']} @ {job['company']}\n"
        f"🔗 {job['url']}"
    )
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_USER_ID,
        "text":    caption,
    }).encode()
    req = urllib.request.Request(msg_url, data=payload,
                                  headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=15)

    # Send each file
    success = True
    for doc_type, path in files.items():
        if not path.exists():
            print(f"  ✗ Missing file: {path.name}")
            success = False
            continue

        # Use multipart form upload
        import mimetypes, io
        boundary = "----JobHunterBoundary"
        mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
            f"{TELEGRAM_USER_ID}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="document"; filename="{path.name}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            urllib.request.urlopen(req, timeout=30)
            print(f"  ✓ Sent via Telegram: {path.name}")
        except Exception as e:
            print(f"  ✗ Telegram upload failed for {path.name}: {e}")
            success = False

    return success


def deliver_via_email(job: dict, files: dict[str, Path]):
    """Send document files to PERSONAL_EMAIL."""
    if not PERSONAL_EMAIL:
        print("  ✗ PERSONAL_EMAIL not set — skipping email delivery")
        return False

    from scripts.email.mail_client import send_documents

    subject = f"JobHunter: Documents for {job['title']} @ {job['company']}"
    body    = (
        f"Your CV and cover letter are attached.\n\n"
        f"Job: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"URL: {job['url']}\n\n"
        f"Files:\n"
        + "\n".join(f"  - {p.name}" for p in files.values() if p.exists())
    )

    existing_files = [p for p in files.values() if p.exists()]
    ok = send_documents(subject=subject, body=body, attachments=existing_files)

    if ok:
        print(f"  ✓ Sent via email to {PERSONAL_EMAIL}")
    else:
        print(f"  ✗ Email delivery failed")
    return ok


def deliver(job_id: str):
    job = fetchone("""
        SELECT id, title, company, url FROM jobs WHERE id = %s
    """, (job_id,))
    if not job:
        print(f"ERROR: Job {job_id} not found.")
        sys.exit(1)

    # Find the application record
    app = fetchone("""
        SELECT id FROM applications WHERE job_id = %s
        ORDER BY generated_at DESC LIMIT 1
    """, (job_id,))

    # Check tmp files — restore from DB if missing
    files = get_tmp_files(job_id)
    all_present = all(p.exists() for p in files.values())

    if not all_present:
        print("  Tmp files missing — restoring from database...")
        if not restore_from_db(job_id):
            print("ERROR: Documents not found in database. Regenerate with generate_application.py")
            sys.exit(1)

    method = load_delivery_method()
    print(f"Delivering documents via: {method}")

    telegram_ok = False
    email_ok    = False

    if method in ("telegram", "both"):
        telegram_ok = deliver_via_telegram(job, files)

    if method in ("email", "both"):
        email_ok = deliver_via_email(job, files)

    # Determine overall success
    if method == "telegram":
        success = telegram_ok
    elif method == "email":
        success = email_ok
    else:
        success = telegram_ok or email_ok  # both: succeed if at least one worked

    delivered_via = []
    if telegram_ok: delivered_via.append("telegram")
    if email_ok:    delivered_via.append("email")

    # Update application record
    if app:
        execute("""
            UPDATE applications
            SET status       = %s,
                delivered_via = %s,
                delivered_at  = NOW(),
                updated_at    = NOW()
            WHERE id = %s
        """, (
            "delivered" if success else "failed",
            "+".join(delivered_via) if delivered_via else None,
            str(app["id"]),
        ))

    if success:
        print(f"\n✓ Documents delivered for: {job['title']} @ {job['company']}")
    else:
        print(f"\n✗ Delivery failed — files are safe in the database, retry with:")
        print(f"  python scripts/email/deliver_documents.py --job-id {job_id}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    deliver(args.job_id)
