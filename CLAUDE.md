# CLAUDE.md — AI Assistant Onboarding Guide

This file brings an AI assistant up to speed on the JobHunter v2 project.
Read this before making any changes. Then read the files listed under "Key files to read first".

---

## What this project is

JobHunter v2 is a self-hosted AI job hunting agent built on [OpenClaw](https://docs.openclaw.ai/).
It scrapes job boards, scores matches against a user profile using a local LLM,
delivers a daily digest via Telegram, and generates tailored CVs and cover letters on demand.

**Repo:** https://github.com/MBojer/OpenClaw_JobHunter
**OpenClaw version:** 2026.3.13

---

## Infrastructure

| Component | Details |
|---|---|
| OpenClaw gateway | Runs on dedicated VMs — see your .env for hostnames |
| PostgreSQL | Remote PostgreSQL — configured in DATABASE_URL in .env |
| Ollama | Remote Ollama — configured in OLLAMA_BASE_URL in .env |
| SearXNG | Self-hosted — configured in SEARXNG_URL in .env |
| Together.ai | ~$10 budget, used ONLY for CV/cover letter generation |
| OpenRouter | Free model `openrouter/stepfun/step-3.5-flash:free` for orchestration |
| Telegram | Each VM has its own dedicated bot — never share bots between installs |

---

## Architecture — three-model design

```
Free model (OpenRouter)     — orchestration, digest, user chat
                              Sees: structured metadata ONLY, never raw content
                              ~1 API call per day

Qwen2.5:7b (Ollama, local)  — job scoring, profile parsing, deduplication
                              Sees: raw job descriptions and profile text
                              Cost: $0, runs on remote Ollama server

Together.ai (paid)          — CV + cover letter generation only
                              Sees: profile.json + job description
                              Budget tracked in spend_log table
```

**Critical rule:** `description_raw` from the jobs table NEVER enters the free model context.

---

## Key files to read first

Before making any changes, read these files from GitHub:

```
https://raw.githubusercontent.com/MBojer/OpenClaw_JobHunter/main/AGENTS.md
https://raw.githubusercontent.com/MBojer/OpenClaw_JobHunter/main/skills/onboarding/SKILL.md
https://raw.githubusercontent.com/MBojer/OpenClaw_JobHunter/main/skills/db-manager/SKILL.md
https://raw.githubusercontent.com/MBojer/OpenClaw_JobHunter/main/scripts/local_llm/score_jobs.py
https://raw.githubusercontent.com/MBojer/OpenClaw_JobHunter/main/scripts/scraping/boards/searxng.py
https://raw.githubusercontent.com/MBojer/OpenClaw_JobHunter/main/db/schema.sql
```

---

## Repo structure

```
/                           — OpenClaw workspace root (repo IS the workspace)
├── AGENTS.md               — Agent operating instructions (loaded every session)
├── SOUL.md                 — Agent persona and tone
├── TOOLS.md                — Tool restrictions and DB query rules
├── IDENTITY.md             — Agent name, emoji, version
├── HEARTBEAT.md            — Gateway restart checklist
├── USER.md                 — User preferences (updated by onboarding)
├── CLAUDE.md               — This file
├── install.sh              — One-liner installer (prereqs inlined, curl-safe)
├── requirements.txt        — Python deps: psycopg2-binary, python-dotenv
├── .env.example            — All required environment variables documented
│
├── install/                — Installer scripts
│   ├── check_prereqs.sh    — Standalone prereqs check (not called by install.sh)
│   ├── setup_env.sh        — Interactive .env wizard
│   ├── setup_telegram.sh   — Bot token + user ID capture, atomic config patch
│   ├── patch_telegram_config.py — Writes all Telegram config atomically
│   ├── setup_cron.py       — Registers cron jobs (requires gateway running)
│   └── verify.sh           — Post-install health check
│
├── patches/                — Incremental patch scripts (preferred over full rewrites)
│   ├── 001_notes.py        — User notes on jobs and applications
│   ├── 002_explicit_digest.py — Explicit digest query in AGENTS.md
│   ├── 003_digest_format.py — Digest display format fixes
│   ├── 004_extract_company_location.py — Extract company/location during scoring
│   ├── 005_searxng_quality.py — SearXNG domain/title blocklists
│   └── 006_searxng_path_filter.py — SearXNG URL path filtering
│
├── scripts/
│   ├── db/
│   │   ├── client.py       — PostgreSQL helper (fetchone, fetchall, execute)
│   │   ├── migrate.py      — Runs schema.sql + numbered migrations
│   │   └── check_budget.py — Together.ai budget guard (exits 1=warn, 2=refuse)
│   ├── local_llm/
│   │   ├── ollama_client.py — Ollama API client, supports json_mode=True
│   │   └── score_jobs.py   — Two-pass: score then dedup. Uses .replace() not .format()
│   ├── onboarding/
│   │   └── parse_profile.py — Qwen parses raw LinkedIn text → structured JSON
│   ├── scraping/
│   │   ├── base_connector.py — Abstract base class for board connectors
│   │   ├── rss_connector.py  — Generic RSS/Atom parser
│   │   ├── run_scrape.py     — Entry point, triggers score_jobs.py after scrape
│   │   └── boards/
│   │       ├── jobindex.py   — Tier 1 RSS (working)
│   │       ├── searxng.py    — Tier 1 JSON API (primary for non-RSS boards)
│   │       ├── indeed.py     — Disabled (403)
│   │       ├── it_jobbank.py — Disabled (HTML scraper needs work)
│   │       └── _template.py  — Copy this to add a new board
│   └── email/
│       ├── mail_client.py        — SMTP send-only to PERSONAL_EMAIL (hardcoded)
│       ├── generate_application.py — Calls Together.ai, stores docs in DB
│       └── deliver_documents.py  — Sends docs via Telegram + email
│
├── skills/                 — OpenClaw skill files loaded into agent context
│   ├── onboarding/SKILL.md — /onboard flow, cron registration during onboarding
│   ├── job-scraper/
│   │   ├── SKILL.md
│   │   └── board_registry.json — Board config, SearXNG enabled, Indeed/IT-jobbank disabled
│   ├── job-filter/
│   │   ├── SKILL.md
│   │   ├── filter_prompt.txt — Qwen scoring prompt (extracts score, company, location)
│   │   └── dedup_prompt.txt  — Qwen dedup prompt (temperature 0.0)
│   ├── cv-writer/
│   │   ├── SKILL.md
│   │   ├── cv_base.md
│   │   └── writer-agent.md   — Together.ai CV/CL generation prompt
│   ├── db-manager/SKILL.md   — Allowed DB columns, standard queries
│   └── email-handler/SKILL.md
│
├── db/
│   ├── schema.sql            — Full schema, idempotent (IF NOT EXISTS throughout)
│   └── migrations/
│       ├── 001_initial.sql
│       ├── 002_schema_update.sql
│       └── 003_notes.sql     — user_note column on jobs and applications
│
├── config/
│   ├── openclaw.template.json — OpenClaw config with exec restrictions
│   ├── profile.example.json   — Structure reference (gitignored when real)
│   └── preferences.example.json
│
└── docs/
    ├── architecture.md
    ├── setup.md
    ├── onboarding.md
    ├── model-strategy.md
    └── adding-a-board.md
```

---

## Database tables

| Table | Purpose |
|---|---|
| `jobs` | Scraped postings — score, tags, company, location, user_note, status |
| `boards` | Registered connectors |
| `run_log` | Cron execution history |
| `applications` | Document generation + delivery tracking, user_note |
| `documents` | Binary file storage (BYTEA) — CV + CL, DB-backed |
| `spend_log` | Together.ai spend tracking |
| `profile` | Single-row user profile + preferences + profile_hash |
| `schema_migrations` | Applied migration versions |

**Never query `description_raw` or `profile.raw_input` from the agent.**

---

## How to make changes

### Preferred: patch scripts
All changes should be made as numbered patch scripts in `patches/`.
This avoids regenerating whole files and reduces copy-paste errors.

Key conventions:
- Patches include `auto_commit()` at the end — no manual git needed
- Large string content (e.g. AGENTS.md rewrites) goes in a separate `.txt` file
  to avoid Python triple-quote nesting issues (see patches/008_agents_content.txt)
- CLAUDE.md should be updated in patches when architecture changes
- `raw.githubusercontent.com` has CDN lag — verify changes on server not via raw URLs

```python
# patches/NNN_description.py
def patch(description, path, old, new):
    # validates anchor exists, skips if already applied, idempotent
    ...
```

Run from workspace root:
```bash
python3 patches/NNN_description.py
```

### When a patch anchor fails
1. Check the exact text with `sed -n 'X,Yp' <file>`
2. Adjust the anchor string to match exactly
3. Or use line-number-based editing (see patch 004 for example)

### After any change
```bash
git add <changed files>
git commit -m "type: description"
git push
```

Gateway must be restarted to pick up changes to AGENTS.md and skill files.

---

## Known issues / current state

- **company/location** — extracted by Qwen during scoring (not from scraper). Run `--rescore` after adding new jobs to backfill.
- **SearXNG** — blocklists iteratively improved via patches. time_range disabled when site_filter is set (combination returns 0 results).
- **Indeed** — disabled, 403 Forbidden. Covered by SearXNG.
- **IT-jobbank** — disabled, HTML selectors need updating.
- **Cron registration** — requires gateway to be running. Agent registers cron during `/onboard`.
- **raw.githubusercontent.com CDN lag** — up to 30 min behind actual commits. Always verify file state on the server, not via raw GitHub URLs.

---

## v2.1 planned

- docx + pdf document generation (currently outputs markdown)
- Reply monitoring (inbox → application status)
- Web dashboard

---

## Conventions

- All scripts use `python3` (not `python`)
- Prompts use `.replace()` not `.format()` — job descriptions contain `{}` characters
- Ollama calls use `json_mode=True` for structured output
- SMTP recipient is always `PERSONAL_EMAIL` from `.env` — never a parameter
- The agent never applies for jobs. Ever.