# Skill: Onboarding

## Purpose
Guide a new user through initial setup of JobHunter. This skill is used once at first
run, or when the user wants to update their profile.

## When to use this skill
- User sends `/onboard`
- User asks to "update my profile" or "redo onboarding"
- `config/profile.json` does not exist yet

## Flow

### Step 1 — Welcome
Greet the user briefly. Explain what JobHunter does in 2-3 sentences.
Ask them to paste their LinkedIn profile (the full text from their LinkedIn "About" +
"Experience" + "Skills" sections). Tell them they can also paste a raw CV.

### Step 2 — Parse (offload to Qwen, do NOT process inline)
Once the user pastes their profile:
1. Save the raw text to a temp file
2. Call: `python3 scripts/onboarding/parse_profile.py --input <tempfile>`
3. This calls Qwen2.5:7b locally. Wait for the result.
4. The script outputs structured JSON to stdout.

**IMPORTANT:** Do not read, summarize, or repeat the raw pasted text back.
Only work with the structured JSON output from the script.

### Step 3 — Confirm with user
Present the structured profile as a clean summary. Example format:
```
Here's what I extracted:
Name: [name]
Current title: [title]
Experience: [N] roles, most recent: [last role] at [last company]
Skills: [top 8 skills]
Location: [location]
```
Ask: "Does this look right? Reply YES to save, or tell me what to correct."

### Step 4 — Preferences
Ask 4 quick questions (one at a time is fine):
1. What job titles are you looking for? (e.g. "Backend Developer, Software Engineer")
2. What's your minimum monthly salary? (DKK or EUR)
3. Preferred location(s) and remote preference?
4. Any keywords to always exclude? (e.g. "junior, unpaid")

### Step 5 — Save
Call: `python3 scripts/onboarding/parse_profile.py --save --profile-json '<json>'`
This writes `config/profile.json` and `config/preferences.json`.
Also inserts/updates the `profile` table in PostgreSQL.

### Step 6 — Discover job boards
Ask the user two questions:
1. "Are you looking for remote, local, or both?"
2. "Which country or region?" (skip if remote only)

Then search for relevant job boards using SearXNG directly:
```python
import sys, json, os, urllib.request, urllib.parse
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
base = os.environ.get('SEARXNG_URL', 'http://localhost')
# Adjust query based on remote/local preference
query = 'best remote job boards software' # or 'job boards Denmark IT'
q = urllib.parse.urlencode({'q': query, 'format': 'json', 'language': 'en'})
req = urllib.request.Request(f'{base}/search?{q}', headers={'Accept': 'application/json'})
data = json.loads(urllib.request.urlopen(req, timeout=10).read())
results = [(r['title'], r['url']) for r in data.get('results', [])[:15]]
print(json.dumps(results))
```
Extract domain names from URLs and present as a numbered list.

Present up to 10 results as a numbered list:
```
Here are job boards I found. Reply with the numbers you want,
ALL for all of them, or NONE to skip:

1. remoteok.com — Remote jobs worldwide
2. weworkremotely.com — Remote jobs
3. jobindex.dk — Danish jobs
4. it-jobbank.dk — Danish IT jobs
...
```

Save selected boards to preferences:
```python
prefs['job_boards'] = ["remoteok.com", "jobindex.dk", ...]
prefs['remote_preference'] = "remote" | "local" | "both"
```

Tell user: "You can manage boards anytime with /boards"

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