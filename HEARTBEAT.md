# Heartbeat

Runs on gateway restart or scheduled heartbeat.
Keep this short — every line costs tokens on every session.

## Checks
- [ ] Are there unscored jobs? Run `python scripts/local_llm/score_jobs.py`
- [ ] Are there undelivered applications? Notify user
- [ ] Is Ollama reachable? If not, warn user via Telegram

## Do NOT do on heartbeat
- Do not run a full scrape (cron handles this)
- Do not generate documents unsolicited
- Do not send a digest unless it is 08:00 cron time
