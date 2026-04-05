# Setup Guide

## Prerequisites

Before installing, make sure you have:

| Requirement | Version | Install |
|---|---|---|
| OpenClaw | 2026.3.13+ | `npm install -g openclaw@latest` |
| Node.js | 22+ | https://nodejs.org |
| Python | 3.10+ | https://python.org |
| Ollama | latest | https://ollama.ai |
| PostgreSQL | 14+ | `apt install postgresql` |
| git | any | `apt install git` |

You also need:
- **OpenRouter API key** (free) — https://openrouter.ai/keys
- **Together.ai API key** with ~$10 loaded — https://api.together.ai
- **A PostgreSQL database** with credentials
- **A dedicated email address** for the agent (e.g. `jobhunter@yourdomain.com`)
- **A Telegram bot** — create one via @BotFather (takes 2 minutes)

---

## Installation

### Option A: One-liner (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/jobhunter-v2/main/install.sh | bash
```

### Option B: Manual

```bash
git clone https://github.com/YOUR_USERNAME/jobhunter-v2.git
cd jobhunter-v2
chmod +x install.sh install/check_prereqs.sh install/setup_env.sh \
         install/setup_telegram.sh install/verify.sh
./install.sh
```

The installer is interactive and will walk you through each step.
It is safe to re-run — it detects existing configuration and updates only what changed.

---

## What gets installed where

| Item | Location |
|---|---|
| Repository = Workspace | `~/.openclaw/workspace-jobhunter/` |
| Skills | `~/.openclaw/workspace-jobhunter/skills/` (in repo) |
| Agent instructions | `~/.openclaw/workspace-jobhunter/AGENTS.md` (in repo) |
| Scripts | `~/.openclaw/workspace-jobhunter/scripts/` (in repo) |
| Generated docs (tmp) | `~/.openclaw/workspace-jobhunter/tmp/` (gitignored) |
| OpenClaw config | `~/.openclaw/openclaw.json` (merged, not replaced) |
| Profile | `~/.openclaw/workspace-jobhunter/config/profile.json` (gitignored) |

The repo IS the workspace — no symlinks needed.
Updating is always: `cd ~/.openclaw/workspace-jobhunter && git pull`

---

## First run

After installing:

1. Start the OpenClaw gateway:
   ```bash
   openclaw gateway
   ```

2. Open your Telegram bot and send `/onboard`

3. The agent sends you a link and a one-time PIN.
   Open the link in your browser and enter the PIN.

4. Complete the 3-step form: profile → job boards → agent setup.
   The last step registers your cron jobs and shuts down the server automatically.

5. That's it. Scrapes and digest run on the schedule you configured (defaults: 07:00, 17:00, 08:00).

---

## Manual scrape (optional)

You can trigger a scrape at any time:

```bash
# Via Telegram: just send
/scrape

# Via command line:
python scripts/scraping/run_scrape.py
```

---

## Updating

To pull the latest version:

```bash
cd ~/jobhunter-v2
git pull
pip install -r requirements.txt --break-system-packages -q
python scripts/db/migrate.py
```

Or just re-run `./install.sh` — it detects the existing install and updates.

---

## Uninstalling

```bash
# Remove the agent from OpenClaw
openclaw agents remove jobhunter

# Remove cron jobs
python install/setup_cron.py --remove  # (add --remove flag in future)

# Remove repo
rm -rf ~/jobhunter-v2

# Optionally remove the workspace
rm -rf ~/.openclaw/workspace-jobhunter
```
