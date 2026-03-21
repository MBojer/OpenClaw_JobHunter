# Skill: Email Handler

## Purpose
Deliver generated CV and cover letter documents to the user
via their configured delivery method (Telegram, email, or both).

## What this skill is NOT
- The agent does NOT send job applications
- The agent does NOT email employers
- The agent does NOT submit forms or apply on the user's behalf
- The agent's role ends at file delivery to the user

## Delivery methods (configured in preferences.json)
- `"telegram"`: files sent as Telegram attachments directly in chat
- `"email"`:    files sent to `PERSONAL_EMAIL` (from .env) as attachments
- `"both"`:     delivers via both channels

## How to deliver documents

```bash
python scripts/email/deliver_documents.py --job-id <uuid>
```

This script:
1. Checks tmp/ for generated files — restores from DB if missing
2. Reads delivery method from `config/preferences.json`
3. Sends via Telegram and/or email depending on method
4. Updates `applications` table with delivery status
5. Files remain in tmp/ until next generation run

## If delivery fails
Files are always stored in the `documents` table first (in `generate_application.py`).
If delivery fails, retry at any time:
```bash
python scripts/email/deliver_documents.py --job-id <uuid>
```
Files will be restored from DB automatically.

## SMTP security
The email recipient is ALWAYS `PERSONAL_EMAIL` from `.env`.
The script accepts no recipient argument — the agent cannot change where files go.

## Rules
- Always confirm with user before calling `deliver_documents.py`
- Never describe the CV or cover letter content in chat (too many tokens)
- After delivery: tell user the files were sent and the job URL for them to apply manually
- The user applies manually — the agent hands over documents only
