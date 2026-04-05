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
Parse the JSON output and extract the `url` field.

### Step 2 — Send the URL to the user
Tell the user:
> Your onboarding form is ready. Open this link in your browser:
> [url from step 1]
>
> Fill in your profile (you can import a PDF/DOCX CV), then select your job boards on the next tab.
> Come back here and say **done** when you're finished.

### Step 3 — Wait for confirmation
Wait for the user to say "done" (any variant: "Done", "finished", "ready", etc.).
Do not prompt with further questions — the form covers everything.

### Step 4 — Stop the web server
Run: `python3 scripts/onboarding/stop_server.py`

Tell user: "✓ Profile saved"

### Step 7 — Register cron jobs
Before finishing, register the scheduled jobs by running each of these commands:

```
openclaw cron add --name jobhunter-morning-scrape --cron "0 7 * * *" --agent jobhunter --message "SYSTEM: Run the job scrape now. Execute: python3 scripts/scraping/run_scrape.py"
openclaw cron add --name jobhunter-evening-scrape --cron "0 17 * * *" --agent jobhunter --message "SYSTEM: Run the job scrape now. Execute: python3 scripts/scraping/run_scrape.py"
openclaw cron add --name jobhunter-digest --cron "0 8 * * *" --agent jobhunter --message "SYSTEM: Run the daily digest. Query top new jobs from the last 24 hours (status='new', not 'duplicate') ORDER BY score DESC LIMIT 10. Format and send the digest to the user."
```

If a job already exists you will get an error — that is fine, skip it.
Tell the user "✓ Cron jobs registered" once done.

### Step 8 — Finish
Confirm saved. Tell the user:
- Scraping runs twice daily (morning and evening)
- They'll get a digest message each morning with top matches
- They can say "apply to job #3" at any time
- Type `/help` to see all commands
- Use `/onboard` again any time to update your profile

## Rules
- Never store the raw LinkedIn paste beyond the temp file
- Never pass raw profile text to any message sent back to the user
- If parsing fails, apologise and ask the user to try pasting again
- Keep all responses short — this is a Telegram chat, not a document