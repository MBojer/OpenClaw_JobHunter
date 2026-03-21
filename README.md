# JobHunter v2 🦞

A self-hosted AI job hunting agent built on [OpenClaw](https://docs.openclaw.ai/).

Scrapes job boards, scores matches against your profile, notifies you via Telegram,
and writes tailored CVs and cover letters on demand — all with minimal API calls.

---

## Architecture at a glance

```
[CRON - automated, free]
  run_scrape.py       → fetches new jobs from all active boards
  score_jobs.py       → Qwen2.5:7b (local) scores each job against your profile

[DAILY DIGEST - 1 free model call]
  orchestrator        → reads DB summary → sends ranked list to Telegram

[ON DEMAND - user triggered]
  "Apply to job #3"   → writer-agent (Together.ai) generates CV + cover letter
                      → user approves → sent from agent mailbox

[ONBOARDING - once]
  user pastes LinkedIn profile → Qwen parses → profile.json confirmed by user
```

**Model responsibilities:**

| Model | Used for | Sees |
|---|---|---|
| Qwen2.5:7b (Ollama, local) | Parsing, scoring, classification | Raw content |
| Free model (OpenRouter) | Orchestration, user chat | Structured metadata only |
| Together.ai (paid) | CV + cover letter writing | Profile + job description |

---

## Prerequisites

- [OpenClaw](https://docs.openclaw.ai/install) `2026.3.13+`
- Node.js `22+`
- Python `3.10+`
- [Ollama](https://ollama.ai) running locally with `qwen2.5:7b` pulled
- PostgreSQL database (with credentials)
- SMTP/IMAP credentials for a dedicated agent email address
- OpenRouter API key (free tier)
- Together.ai API key (~$10 loaded)
- A Telegram bot token (create via [@BotFather](https://t.me/BotFather))

---

## One-liner install

```bash
curl -fsSL https://raw.githubusercontent.com/MBojer/OpenClaw_JobHunter/main/install.sh | bash
```

Or clone and run manually:

```bash
git clone https://github.com/MBojer/OpenClaw_JobHunter.git ~/.openclaw/workspace-jobhunter
cd ~/.openclaw/workspace-jobhunter
chmod +x install.sh
./install.sh
```

> The repo is cloned directly into your OpenClaw workspace.
> This means `git pull` updates everything — skills, agent instructions, scripts — in one command.

---

## What the installer does

1. Checks prerequisites (Node, Python, Ollama, psql)
2. Walks you through `.env` setup interactively
3. Runs database migrations
4. Pulls `qwen2.5:7b` if not already present
5. Symlinks `skills/` into your OpenClaw workspace
6. Registers the JobHunter agent via `openclaw agents add`
7. Configures Telegram bot + captures your user ID automatically
8. Registers cron jobs
9. Runs a health check

Re-running the installer is safe — it detects existing config and updates only what changed.

---

## First run

After installing, send your bot a message in Telegram:

```
/start
```

The agent will walk you through onboarding — paste your LinkedIn profile when prompted.

---

## Adding a job board

See [`docs/adding-a-board.md`](docs/adding-a-board.md).

---

## Model cost guide

- **OpenRouter free model:** ~1 call/day for digest + user interactions. No cost.
- **Qwen2.5:7b:** Runs locally. No cost.
- **Together.ai:** Only used for CV/cover letter generation.
  Budget is tracked — you'll be warned before it runs low.

---

## Roadmap

- **v2.1:** Reply monitoring (inbox → application status updates), web dashboard

---

## License

MIT
