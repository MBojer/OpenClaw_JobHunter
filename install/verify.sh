#!/usr/bin/env bash
# install/verify.sh — Post-install health check
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0

GREEN="\033[32m"; RED="\033[31m"; YELLOW="\033[33m"; RESET="\033[0m"

ok()   { echo -e "  ${GREEN}✓${RESET} $*"; }
fail() { echo -e "  ${RED}✗${RESET} $*"; FAIL=1; }
warn() { echo -e "  ${YELLOW}⚠${RESET}  $*"; }

echo ""
echo "Running health checks..."
echo ""

# Load .env
if [ -f "$INSTALL_DIR/.env" ]; then
    set -a; source "$INSTALL_DIR/.env"; set +a
else
    fail ".env not found"
fi

# ── Python imports ───────────────────────────────────────────────────────────
if python3 -c "import psycopg2, dotenv" 2>/dev/null; then
    ok "Python dependencies (psycopg2, dotenv)"
else
    fail "Python dependencies missing — run: pip install -r requirements.txt --break-system-packages"
fi

# ── Database connection ──────────────────────────────────────────────────────
if python3 -c "
import os, sys
os.chdir('$INSTALL_DIR')
sys.path.insert(0, '.')
from scripts.db.client import fetchone
r = fetchone('SELECT version()')
print('  DB:', r['version'][:40])
" 2>/dev/null; then
    ok "PostgreSQL connection"
else
    fail "PostgreSQL connection failed — check DATABASE_URL in .env"
fi

# ── Schema ───────────────────────────────────────────────────────────────────
if python3 -c "
import os, sys
os.chdir('$INSTALL_DIR')
sys.path.insert(0, '.')
from scripts.db.client import fetchall
tables = [r['tablename'] for r in fetchall(\"SELECT tablename FROM pg_tables WHERE schemaname='public'\")]
required = {'jobs','boards','run_log','applications','spend_log','profile'}
missing = required - set(tables)
if missing:
    print('Missing tables:', missing)
    sys.exit(1)
" 2>/dev/null; then
    ok "Database schema (all tables present)"
else
    fail "Database schema incomplete — run: python3 scripts/db/migrate.py"
fi

# ── Processing LLM ───────────────────────────────────────────────────────────
if curl -sf "${PROC_LLM_BASE_URL:-http://localhost:11434}/api/tags" >/dev/null; then
    ok "Processing LLM reachable at ${PROC_LLM_BASE_URL:-http://localhost:11434}"
else
    fail "Processing LLM not reachable — check PROC_LLM_BASE_URL in .env"
fi

MODEL="${PROC_LLM_MODEL:-qwen2.5:7b}"
if python3 -c "
import os, sys
os.chdir('$INSTALL_DIR')
sys.path.insert(0, '.')
from scripts.local_llm.ollama_client import model_is_pulled
sys.exit(0 if model_is_pulled() else 1)
" 2>/dev/null; then
    ok "Processing LLM model ($MODEL) is available"
else
    warn "Processing LLM model ($MODEL) not found — ensure it is loaded on the server"
fi

# ── Workspace is git repo ────────────────────────────────────────────────────
WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace-jobhunter}"
if [ -d "$WORKSPACE/.git" ]; then
    REMOTE=$(git -C "$WORKSPACE" remote get-url origin 2>/dev/null || echo "")
    ok "Workspace is a git repo: $REMOTE"
else
    fail "Workspace is not a git repo — re-run install.sh to clone correctly"
fi

# ── OpenClaw agent ───────────────────────────────────────────────────────────
if openclaw agents list --json 2>/dev/null | grep -q '"jobhunter"'; then
    ok "OpenClaw agent 'jobhunter' registered"
else
    fail "OpenClaw agent not found — re-run install.sh"
fi

# ── Telegram token ───────────────────────────────────────────────────────────
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    if curl -sf "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" | grep -q '"ok":true'; then
        BOT_USERNAME=$(curl -sf "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" \
            | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['username'])")
        ok "Telegram bot @${BOT_USERNAME} is reachable"
    else
        fail "Telegram bot token invalid or bot is unreachable"
    fi
else
    warn "TELEGRAM_BOT_TOKEN not set — run install/setup_telegram.sh"
fi

# ── Telegram user ID ─────────────────────────────────────────────────────────
if [ -n "${TELEGRAM_USER_ID:-}" ]; then
    ok "Telegram user ID configured: $TELEGRAM_USER_ID"
else
    warn "TELEGRAM_USER_ID not set — run install/setup_telegram.sh"
fi

# ── Together.ai ──────────────────────────────────────────────────────────────
if [ -n "${TOGETHER_API_KEY:-}" ]; then
    ok "Together.ai API key set (budget: \$${TOGETHER_BUDGET_USD:-10.00})"
else
    fail "TOGETHER_API_KEY not set — CV/cover letter generation will not work"
fi

# ── Budget check ─────────────────────────────────────────────────────────────
python3 "$INSTALL_DIR/scripts/db/check_budget.py" 2>/dev/null \
    && ok "Budget check passed" \
    || warn "Budget check warning — see above"

# ── Cron jobs ────────────────────────────────────────────────────────────────
# Cron jobs are registered AFTER the gateway is started (Gateway RPC required).
# Run: python3 install/setup_cron.py  (once the gateway is running)
CRON_STORE="$HOME/.openclaw/cron/jobs.json"
if [ -f "$CRON_STORE" ]; then
    ok "Cron store exists — jobs registered"
else
    warn "Cron jobs not yet registered — run: python3 install/setup_cron.py (after starting gateway)"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}All checks passed. JobHunter is ready!${RESET}"
    echo ""
    echo "  Start the gateway:    openclaw gateway"
    echo "  Then message your bot: /start"
else
    echo -e "${RED}Some checks failed. Please fix the issues above.${RESET}"
    exit 1
fi