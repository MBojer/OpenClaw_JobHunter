"""
scripts/email/mail_client.py
SMTP send-only client for the agent's dedicated mailbox.

IMPORTANT SECURITY RULE:
  This script may ONLY send to PERSONAL_EMAIL from .env.
  The recipient address is never passed as a parameter — it is always
  read from the environment. The agent cannot change where files go.

v2.0: document delivery to personal address only.
"""
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.base      import MIMEBase
from email                import encoders
from pathlib              import Path
from dotenv               import load_dotenv

load_dotenv()

# ── Config — all from .env, never from caller ─────────────────────────────────
SMTP_HOST      = os.environ["SMTP_HOST"]
SMTP_PORT      = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER      = os.environ["SMTP_USER"]
SMTP_PASS      = os.environ["SMTP_PASS"]
FROM_EMAIL     = os.environ["AGENT_EMAIL"]
FROM_NAME      = os.environ.get("SMTP_FROM_NAME", "Job Hunter")
PERSONAL_EMAIL = os.environ["PERSONAL_EMAIL"]   # Hardcoded destination — never overridden


def send_documents(
    subject:     str,
    body:        str,
    attachments: list[Path],
) -> bool:
    """
    Send document files to PERSONAL_EMAIL.
    Returns True on success, False on failure.
    Recipient is always PERSONAL_EMAIL — callers cannot override this.
    """
    msg = MIMEMultipart()
    msg["From"]    = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"]      = PERSONAL_EMAIL
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    for path in attachments:
        if not path.exists():
            raise FileNotFoundError(f"Attachment not found: {path}")
        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{path.name}"',
        )
        msg.attach(part)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, PERSONAL_EMAIL, msg.as_string())
        return True
    except smtplib.SMTPException as e:
        print(f"SMTP error: {e}")
        return False
