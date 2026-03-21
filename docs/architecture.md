# Architecture

## Overview

JobHunter v2 is a self-hosted AI job hunting agent built on OpenClaw.
Designed around three core constraints:

1. **Minimal free model API calls** — orchestrator runs ~once per day
2. **No raw content in the agent context** — privacy and token efficiency  
3. **Local-first processing** — Qwen handles all heavy lifting for free

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER                                    │
│              Telegram DM / OpenClaw Web UI                      │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                    OPENCLAW GATEWAY                             │
│  Agent: jobhunter                                               │
│  Skills: onboarding, job-scraper, job-filter,                   │
│          cv-writer, db-manager, email-handler                   │
│  System prompt: agents/orchestrator.md                          │
│                                                                 │
│  Model: openrouter/stepfun/step-3.5-flash:free                  │
│  Sees: structured metadata ONLY — never raw content             │
└──────┬───────────────────────────────────┬───────────────────────┘
       │ triggers                          │ queries
┌──────▼──────────────┐         ┌──────────▼────────────────────┐
│   Python Scripts    │         │        PostgreSQL              │
│                     │         │                               │
│  run_scrape.py      │◄────────│  boards        run_log        │
│  score_jobs.py      │         │  jobs          applications   │
│  parse_profile.py   │         │  profile       spend_log      │
│  generate_app.py    │         │  documents                    │
│  deliver_docs.py    │         │                               │
└──────┬──────────────┘         └───────────────────────────────┘
       │ calls
┌──────▼──────────────────────────────────────────────────────┐
│              OLLAMA — Qwen2.5:7b (LOCAL, FREE)              │
│  Scores jobs, parses profiles, deduplicates cross-posts     │
│  Sees: raw job descriptions, raw profile text               │
│  Runs on: your RTX 3060 — zero API cost                     │
└─────────────────────────────────────────────────────────────┘

(on-demand, user-triggered only)
┌──────────────────────────────────────────────────────────────┐
│              TOGETHER.AI — Llama 3.3 70B                     │
│  Generates CV + cover letter only                            │
│  Sees: profile.json + job description                        │
│  Cost: ~$0.004 per application — budget tracked in DB        │
└─────────────────────────────────────────────────────────────┘

(document delivery — to user only)
┌──────────────────────────────────────────────────────────────┐
│              AGENT MAILBOX (SMTP send-only)                  │
│  Sends finished documents to PERSONAL_EMAIL                  │
│  Recipient is hardcoded in .env — agent cannot change it     │
│  Also delivers via Telegram if method = "telegram" or "both" │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Onboarding (once)
```
User pastes LinkedIn text in Telegram
  → Saved to temp file (never enters agent context)
  → parse_profile.py → Qwen parses → structured JSON
  → Agent presents summary → user confirms
  → Saved to config/profile.json + profile DB table
  → profile_hash computed and stored
  → preferences.json collected via Q&A
```

### Daily scrape (07:00 + 17:00 — fully automated)
```
Cron → run_scrape.py
  → Reads board_registry.json
  → Each connector fetches via RSS or HTML
  → Deduplication: skip URLs already in DB
  → New jobs inserted: status='new', score=NULL

  → Automatically calls score_jobs.py

score_jobs.py — Pass 1: Scoring
  → SELECT unscored jobs (including description_raw — Qwen only)
  → For each: build prompt, send to Qwen
  → Returns: score (0-100), tags, one-line reason
  → UPDATE jobs: score, tags, score_reason, scored_at

score_jobs.py — Pass 2: Deduplication
  → For each newly scored job: find other jobs from same company (last 30 days)
  → If candidates exist: ask Qwen "same posting?"
  → If YES: mark newer job status='duplicate', duplicate_of=<original_id>
  → Duplicates kept in DB — never shown in digest
```

### Daily digest (08:00 — 1 free model call)
```
Cron sends message to orchestrator agent

Orchestrator queries DB:
  SELECT title, company, location, remote, score, score_reason, tags, url
  FROM jobs
  WHERE status = 'new'      ← excludes duplicates
    AND score >= min_score
    AND scraped_at > NOW() - INTERVAL '24 hours'
  ORDER BY score DESC LIMIT 10
  ← description_raw is NEVER selected

Formats digest → sends to Telegram
```

### Document generation + delivery (user-triggered)
```
User: "/apply 3"

Orchestrator:
  1. Checks budget (check_budget.py — direct import, no subprocess)
  2. Confirms with user
  3. Calls generate_application.py --job-id <uuid>
     → Cleans tmp/ directory first
     → Calls Together.ai: profile.json + job description → CV + CL
     → Writes files to ~/.openclaw/workspace-jobhunter/tmp/
     → Stores files as BYTEA in documents table (DB-backed, safe)
     → Logs spend to spend_log
     → Shows 3-line cover letter preview
  4. Asks: "YES to deliver / EDIT to revise / CANCEL"

On YES:
  5. Calls deliver_documents.py --job-id <uuid>
     → Reads delivery method from preferences.json
     → Telegram: sends files as attachments to TELEGRAM_USER_ID
     → Email: sends to PERSONAL_EMAIL via SMTP (hardcoded, agent cannot change)
     → Updates applications table: delivered_via, delivered_at
  6. Tells user: "Files delivered ✓. Apply here: [url]"

THE AGENT DOES NOT APPLY. The user applies manually at the job URL.
```

---

## What Each Model Sees

| Model | Input | Never sees |
|---|---|---|
| Free model (orchestrator) | Structured DB summaries, user messages | description_raw, raw profile, CV/CL text |
| Qwen2.5:7b (local) | Raw job descriptions, raw profile text | Nothing restricted — runs locally |
| Together.ai | profile.json + job description | Email, other jobs, session history |

---

## Security Properties

| Property | How enforced |
|---|---|
| Agent cannot apply for jobs | Hard rule in orchestrator.md + no send script exists |
| Agent cannot email third parties | `mail_client.py` reads `PERSONAL_EMAIL` from env — no recipient arg |
| Raw job text never in agent context | `description_raw` excluded by skill rules + orchestrator instruction |
| Documents survive reinstall | Stored as BYTEA in `documents` table — DB is backed up daily |
| Telegram locked to one user | `dmPolicy: allowlist` + numeric `allowFrom` — set at install time |

---

## Database Tables

| Table | Purpose |
|---|---|
| `boards` | Registered job board connectors |
| `jobs` | All scraped postings — score, tags, dedup status |
| `run_log` | Cron execution history |
| `applications` | Document generation + delivery tracking |
| `documents` | Binary file storage (BYTEA) — CV + CL per application |
| `spend_log` | Together.ai API spend tracking |
| `profile` | User profile + preferences + profile_hash |
| `schema_migrations` | Applied migration versions |

---

## v2.1 Planned
- **docx + pdf generation**: proper document formatting via python-docx + weasyprint
- **Web dashboard**: read-only view of jobs and applications
