# Skill: Onboarding

## Purpose
Guide a new user through initial setup of JobHunter. This skill is used once at first
run, or when the user wants to update their profile.

## When to use this skill
- User sends `/onboard`
- User asks to "update my profile" or "redo onboarding"
- `config/profile.json` does not exist yet

## Flow

### Step 1 — Start the web server
Run: `python3 scripts/onboarding/start_server.py`
Parse the JSON output and extract the `url` and `pin` fields.

### Step 2 — Send the URL and PIN to the user
Tell the user:
> Your onboarding form is ready. Open this link in your browser:
> [url from step 1]
> PIN: [pin from step 1] ← enter this on the first page
>
> Complete all 3 steps in the browser (profile → job boards → agent setup).
> The last step registers your cron jobs and shuts down the server automatically.
> **You don't need to come back here** — everything is handled in the browser.

### Step 3 — Done
Tell the user: "✓ Setup will complete automatically once you finish the browser steps."

## Rules
- Never store the raw LinkedIn paste beyond the temp file
- Never pass raw profile text to any message sent back to the user
- If parsing fails, apologise and ask the user to try pasting again
- Keep all responses short — this is a Telegram chat, not a document
- Do NOT manually run `openclaw cron add` — cron registration is handled by the web UI
