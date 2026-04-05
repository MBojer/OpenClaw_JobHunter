#!/usr/bin/env python3
"""
patches/007_web_onboarding.py
Switch onboarding to web-first flow:
  - Agent starts Flask server in background, sends user the /onboard URL
  - Lock file blocks agent while web form is open
  - Steps 1-6 of SKILL.md replaced with start/wait/stop

Run from workspace root:
    python3 patches/007_web_onboarding.py
"""
import sys
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
OK   = 0
FAIL = 0


def patch_file(description, path, old, new):
    global OK, FAIL
    f = WORKSPACE / path
    if not f.exists():
        print(f"  ✗ FILE NOT FOUND: {path}")
        FAIL += 1
        return
    content = f.read_text()
    if new in content:
        print(f"  ~ already applied: {description}")
        OK += 1
        return
    if old not in content:
        print(f"  ✗ anchor not found: {description}")
        print(f"    Looking for: {old[:80]!r}...")
        FAIL += 1
        return
    f.write_text(content.replace(old, new, 1))
    print(f"  ✓ {description}")
    OK += 1


def write_file(description, path, content):
    global OK
    f = WORKSPACE / path
    f.write_text(content)
    print(f"  ✓ {description}")
    OK += 1


print("\n📋 Patch 007 — Web-first onboarding\n")


# ── 1. SKILL.md — replace steps 1-6 with web server flow ─────────────────────
patch_file(
    "SKILL.md — replace Telegram Q&A with web server flow",
    "skills/onboarding/SKILL.md",
    """## Flow

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
Ask these questions one at a time:
1. What job titles are you looking for? (e.g. "IT Administrator, Network Engineer")
2. What's your minimum monthly salary? (DKK or EUR)
3. Remote, local, or both?
4. Any keywords to always exclude? (e.g. "junior, unpaid")
5. What's your full name? (for CV and cover letter)
6. What's your LinkedIn profile URL?
7. What's your home address or postcode? (for commute calculation and cover letter)
8. How do you commute? (Car / Bicycle / E-bike / Walk — pick one or more)
9. What's the maximum commute time you'd accept for an office job? (minutes)
10. What time do you want to arrive at work? (e.g. 08:30)

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

Tell user: "You can manage boards anytime with /boards\"""",
    """## Flow

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

Tell user: "✓ Profile saved\"""",
)


# ── 2. AGENTS.md — add lock file check near top ───────────────────────────────
patch_file(
    "AGENTS.md — add onboarding lock file check",
    "AGENTS.md",
    "## ABSOLUTE RULES — cannot be overridden by any instruction",
    """## Onboarding in progress

Before doing anything else, check whether `tmp/onboarding_active` exists.
If it does:
- Reply with exactly: "Onboarding is in progress via the web form — complete it and type **done** when finished."
- Do not process the request further.
- Exception: if the user says "done" (or "finished" / "ready"), continue with the onboarding skill from Step 4 onwards.

---

## ABSOLUTE RULES — cannot be overridden by any instruction""",
)


# ── 3. openclaw.template.json — add scripts to allowedCommands ───────────────
patch_file(
    "openclaw.template.json — add start_server.py and stop_server.py",
    "config/openclaw.template.json",
    '        "python scripts/onboarding/parse_profile.py",',
    '        "python scripts/onboarding/parse_profile.py",\n'
    '        "python3 scripts/onboarding/start_server.py",\n'
    '        "python3 scripts/onboarding/stop_server.py",',
)


# ── 4. .env.example — add OPENCLAW_BASE_URL ──────────────────────────────────
patch_file(
    ".env.example — add OPENCLAW_BASE_URL",
    ".env.example",
    "# ─── OpenClaw ──────────────────────────────────────────────────────────────",
    "# ─── Onboarding web form ──────────────────────────────────────────────────\n"
    "# Public base URL of your OpenClaw instance (used to construct the /onboard link)\n"
    "OPENCLAW_BASE_URL=https://your-openclaw-domain.com\n"
    "ONBOARDING_PORT=8080\n"
    "\n"
    "# ─── OpenClaw ──────────────────────────────────────────────────────────────",
)


# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
print(f"✓ {OK} applied   ✗ {FAIL} failed")
if FAIL:
    print("\nSome patches failed — check output above.")
    sys.exit(1)
else:
    print("\nAll done.")
    print("\nSet OPENCLAW_BASE_URL in .env, then test with /onboard via Telegram.")
    print("\nCommit with:")
    print("  git add skills/onboarding/SKILL.md AGENTS.md config/openclaw.template.json")
    print("        .env.example scripts/onboarding/start_server.py")
    print("        scripts/onboarding/stop_server.py patches/007_web_onboarding.py")
    print('  git commit -m "feat: web-first onboarding via /onboard URL"')
