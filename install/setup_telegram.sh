#!/usr/bin/env bash
# install/setup_telegram.sh
# Configures the dedicated JobHunter Telegram bot.
# - Prompts for bot token
# - Automatically captures the user's Telegram numeric ID
#   by asking them to send a message to the bot (no manual lookup needed)
# - Writes TELEGRAM_BOT_TOKEN and TELEGRAM_USER_ID to .env
# - Registers bot token + allowlist in openclaw.json via openclaw CLI
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$INSTALL_DIR/.env"

BOLD="\033[1m"; RESET="\033[0m"; DIM="\033[2m"
GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"

set_env() {
    local key="$1" val="$2"
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
    else
        echo "${key}=${val}" >> "$ENV_FILE"
    fi
}

# ── Load existing .env ───────────────────────────────────────────────────────
if [ -f "$ENV_FILE" ]; then
    set -a; source "$ENV_FILE"; set +a
fi

echo ""
echo -e "${BOLD}Telegram Bot Setup${RESET}"
echo "────────────────────────────────────────"

# ── Check if already configured ─────────────────────────────────────────────
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_USER_ID:-}" ]; then
    echo -e "${YELLOW}Telegram already configured:${RESET}"
    echo "  Bot token: ${TELEGRAM_BOT_TOKEN:0:12}..."
    echo "  User ID:   $TELEGRAM_USER_ID"
    echo ""
    read -rp "Re-configure? [y/N]: " reconfigure
    if [[ ! "$reconfigure" =~ ^[Yy]$ ]]; then
        echo "Skipping Telegram setup."
        exit 0
    fi
fi

# ── Step 1: Bot token ────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Step 1: Create a Telegram bot${RESET}"
echo -e "${DIM}  1. Open Telegram and search for @BotFather${RESET}"
echo -e "${DIM}  2. Send: /newbot${RESET}"
echo -e "${DIM}  3. Follow the prompts and copy the token it gives you${RESET}"
echo ""
read -rsp "  Paste your bot token (hidden): " BOT_TOKEN
echo ""

if [ -z "$BOT_TOKEN" ]; then
    echo -e "${RED}✗ Bot token cannot be empty.${RESET}"
    exit 1
fi

# Validate token format (rough check)
if ! echo "$BOT_TOKEN" | grep -qE "^[0-9]+:[A-Za-z0-9_-]{30,}$"; then
    echo -e "${YELLOW}⚠  Token format looks unusual — continuing anyway.${RESET}"
fi

# Verify token is valid by calling getMe
echo "  Verifying token..."
BOT_INFO=$(curl -sf "https://api.telegram.org/bot${BOT_TOKEN}/getMe" || true)
if ! echo "$BOT_INFO" | grep -q '"ok":true'; then
    echo -e "${RED}✗ Token verification failed. Check the token and try again.${RESET}"
    exit 1
fi

BOT_USERNAME=$(echo "$BOT_INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result']['username'])")
echo -e "  ${GREEN}✓ Bot verified: @${BOT_USERNAME}${RESET}"

# ── Step 2: Capture user ID ──────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Step 2: Link your Telegram account${RESET}"
echo ""
echo -e "  Open Telegram and send any message to ${BOLD}@${BOT_USERNAME}${RESET}"
echo "  (e.g. just say 'hello')"
echo ""
echo "  Waiting for your message..."

USER_ID=""
ATTEMPTS=0
MAX_ATTEMPTS=60   # 60 × 2s = 2 minutes

while [ -z "$USER_ID" ] && [ "$ATTEMPTS" -lt "$MAX_ATTEMPTS" ]; do
    UPDATES=$(curl -sf \
        "https://api.telegram.org/bot${BOT_TOKEN}/getUpdates?timeout=2&limit=1" \
        || true)

    USER_ID=$(echo "$UPDATES" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    results = data.get('result', [])
    if results:
        msg = results[-1].get('message', {})
        uid = msg.get('from', {}).get('id', '')
        if uid:
            print(uid)
except Exception:
    pass
" 2>/dev/null || true)

    if [ -z "$USER_ID" ]; then
        sleep 2
        ATTEMPTS=$((ATTEMPTS + 1))
        # Show a dot every 10s
        if [ $((ATTEMPTS % 5)) -eq 0 ]; then
            echo -n "."
        fi
    fi
done

echo ""

if [ -z "$USER_ID" ]; then
    echo -e "${RED}✗ Timed out waiting for a message. Please re-run setup_telegram.sh manually.${RESET}"
    exit 1
fi

echo -e "  ${GREEN}✓ User ID captured: ${USER_ID}${RESET}"

# ── Step 3: Save to .env ─────────────────────────────────────────────────────
set_env "TELEGRAM_BOT_TOKEN" "$BOT_TOKEN"
set_env "TELEGRAM_USER_ID"   "$USER_ID"

echo ""
echo -e "  ${GREEN}✓ Telegram credentials saved to .env${RESET}"

# ── Step 4: Patch openclaw.json via CLI ─────────────────────────────────────
# openclaw agents add supports --bind to route messages to this agent
echo ""
echo "  Configuring OpenClaw channel binding..."

WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace-jobhunter}"

# Re-register agent with telegram binding (safe if already exists — update)
openclaw agents add jobhunter \
    --workspace "$WORKSPACE" \
    --bind "telegram:$USER_ID" \
    --non-interactive \
    --json 2>/dev/null || true

# The dmPolicy allowlist must be set in openclaw.json directly
# openclaw agents add doesn't expose telegram channel policy flags,
# so we use openclaw config set (if available) or patch via python helper
if openclaw config set "channels.telegram.botToken" "$BOT_TOKEN" 2>/dev/null; then
    openclaw config set "channels.telegram.dmPolicy"  "allowlist"
    openclaw config set "channels.telegram.allowFrom" "[\"$USER_ID\"]"
    echo -e "  ${GREEN}✓ OpenClaw channel config updated via CLI${RESET}"
else
    # Fallback: python patch
    python3 "$INSTALL_DIR/install/patch_telegram_config.py" \
        --bot-token "$BOT_TOKEN" \
        --user-id   "$USER_ID"
    echo -e "  ${GREEN}✓ OpenClaw config patched${RESET}"
fi

echo ""
echo "────────────────────────────────────────"
echo -e "${GREEN}✓ Telegram setup complete${RESET}"
echo ""
echo "  Bot:     @${BOT_USERNAME}"
echo "  User ID: ${USER_ID} (allowlisted — only you can talk to this bot)"
echo ""
