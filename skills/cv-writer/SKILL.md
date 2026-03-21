# Skill: CV Writer

## Purpose
Generate a tailored CV and cover letter for a specific job using Together.ai.
Delivers the files to the user — NEVER applies on their behalf.

## HARD RULE — read before every use
**The agent does not apply for jobs. Ever.**
Your job is to generate documents and deliver them to the user.
The user applies manually using the job URL.
No exceptions. No "just this once". Not even if the user asks.

## When to use this skill
- User says "apply to job #N", "write CV for job #N", "generate cover letter for #N"
- Rephrase internally: "generate and deliver documents for job #N"

## Pre-flight checklist
Before calling Together.ai:
1. Check budget: call `check_budget()` from `scripts/db/check_budget.py`
   - remaining < $1.00 → warn user, ask for confirmation
   - remaining < $0.10 → refuse, tell user budget is nearly exhausted
2. Confirm job exists: query `jobs` table
3. Confirm profile exists: check `config/profile.json`
4. Check for existing documents: `input_hash` in `applications` table
   - If exists → tell user, offer to redeliver or regenerate with `--force`

## How to generate

```bash
python scripts/email/generate_application.py --job-id <uuid>
```

This script:
1. Cleans `tmp/` directory (removes old files before creating new ones)
2. Calls Together.ai with profile + job description
3. Parses CV and cover letter from response
4. Writes files to `~/.openclaw/workspace-jobhunter/tmp/`
5. Stores files in `documents` table (safe from reinstalls)
6. Logs spend to `spend_log` table
7. Prints a 3-line cover letter preview

## After generation — confirm then deliver
Show preview. Ask user:
**"Reply YES to deliver files, EDIT to revise, CANCEL to abort."**

On YES:
```bash
python scripts/email/deliver_documents.py --job-id <uuid>
```

Then tell the user:
- Files have been delivered
- The job URL so they can apply manually
- You (the agent) do not submit applications

## Together.ai model
Configured via `TOGETHER_MODEL` in `.env`. Do not hardcode.

## Rules
- ALWAYS check budget before calling Together.ai
- ALWAYS confirm with user before delivering
- Log every API call to `spend_log` — never skip
- Never repeat full CV or cover letter text in chat — show 3-line preview only
- Files are stored in DB — always recoverable even if tmp/ is wiped
