# Onboarding

Onboarding collects your professional profile, job preferences, and registers the scheduled agent jobs.
It runs once at first launch, and can be re-run any time via `/onboard`.

---

## How to start

Send `/onboard` to the Telegram bot.

The agent generates a one-time PIN and sends you a link to a secure web form.
Everything is done in the browser — no pasting into Telegram.

---

## The 3-step browser flow

### Step 1 — Profile

Enter your PIN, then set up your professional profile:

- **Import from CV/LinkedIn** — upload a PDF or DOCX, or paste raw text; Qwen2.5 extracts structured data locally
- **Fill manually** — enter job titles, experience, skills, education, location

Adjust preferences: job titles you're targeting, salary floor, remote preference, commute limits, excluded keywords, digest size, and minimum score threshold.

Click **Validate & Review** to check for issues, then **Save Profile** to continue.

### Step 2 — Job Boards

Enable or disable each job board. Configure SearXNG site filtering — choose from curated domains or add your own. Advanced options: search engines, time range, language.

Click **Save Settings** to continue.

### Step 3 — Agent Setup

Set the schedule for automated jobs:

| Job | Default | Description |
|---|---|---|
| Morning Scrape | 07:00 | Scrapes all active boards and scores postings |
| Evening Scrape | 17:00 | Second daily pass — can be disabled |
| Daily Digest | 08:00 | Sends top matches to Telegram |

Adjust times with the hour dropdowns. Toggle the Evening Scrape off if once-daily is enough.

Click **Setup Agent** to register the cron jobs, then **Close & Finish** to shut down the onboarding server.

---

## Re-running onboarding

Send `/onboard` again at any time to update your profile, boards, or schedule.
Re-running will re-score all existing jobs against your updated profile.

---

## Privacy notes

- Raw CV/LinkedIn text is processed by **Qwen2.5:7b on your own machine**
- The free cloud model (OpenRouter) **never sees** your raw profile
- Together.ai sees `profile.json` (structured data only) when generating a CV/cover letter
- Raw input is stored in `profile.raw_input` (DB) for re-parsing, never shown in chat
