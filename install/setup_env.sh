#!/usr/bin/env bash
# install/setup_env.sh — Interactive .env wizard
# Walks the user through all required config values
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$INSTALL_DIR/.env"
EXAMPLE_FILE="$INSTALL_DIR/.env.example"

BOLD="\033[1m"; RESET="\033[0m"; DIM="\033[2m"; YELLOW="\033[33m"

prompt() {
    # prompt <var_name> <display_name> <description> [default]
    local var="$1" label="$2" desc="$3" default="${4:-}"
    echo ""
    echo -e "${BOLD}$label${RESET}"
    echo -e "${DIM}$desc${RESET}"
    if [ -n "$default" ]; then
        read -rp "  Value [$default]: " val
        val="${val:-$default}"
    else
        read -rp "  Value: " val
        while [ -z "$val" ]; do
            echo "  This field is required."
            read -rp "  Value: " val
        done
    fi
    # Write to .env (append or update)
    if grep -q "^${var}=" "$ENV_FILE" 2>/dev/null; then
        sed -i "s|^${var}=.*|${var}=\"${val}\"|" "$ENV_FILE"
    else
        echo "${var}=\"${val}\"" >> "$ENV_FILE"
    fi
}

prompt_secret() {
    local var="$1" label="$2" desc="$3"
    echo ""
    echo -e "${BOLD}$label${RESET}"
    echo -e "${DIM}$desc${RESET}"
    read -rsp "  Value (hidden): " val
    echo ""
    while [ -z "$val" ]; do
        echo "  This field is required."
        read -rsp "  Value (hidden): " val
        echo ""
    done
    if grep -q "^${var}=" "$ENV_FILE" 2>/dev/null; then
        sed -i "s|^${var}=.*|${var}=\"${val}\"|" "$ENV_FILE"
    else
        echo "${var}=\"${val}\"" >> "$ENV_FILE"
    fi
}

# ── Start from example ───────────────────────────────────────────────────────
cp "$EXAMPLE_FILE" "$ENV_FILE"
echo ""
echo -e "${BOLD}JobHunter .env setup${RESET}"
echo "────────────────────────────────────────"
echo "I'll ask for each required setting."
echo "Press Enter to accept the default where shown."
echo ""

# ── OpenRouter ───────────────────────────────────────────────────────────────
echo -e "${YELLOW}── OpenRouter (free model) ──${RESET}"
prompt_secret "OPENROUTER_API_KEY" \
    "OpenRouter API Key" \
    "Free tier key from https://openrouter.ai/keys"

prompt "OPENROUTER_MODEL" \
    "OpenRouter Model" \
    "Free model to use for orchestration" \
    "openrouter/stepfun/step-3.5-flash:free"

# ── Together.ai ──────────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}── Together.ai (CV writing only) ──${RESET}"
prompt_secret "TOGETHER_API_KEY" \
    "Together.ai API Key" \
    "From https://api.together.ai — used only for CV/cover letter generation"

prompt "TOGETHER_BUDGET_USD" \
    "Together.ai Budget (USD)" \
    "Total budget to spend — the agent will warn you when running low" \
    "10.00"

prompt "TOGETHER_WARN_AT_USD" \
    "Warn when budget drops below (USD)" \
    "Get a warning when this much budget remains" \
    "1.00"

# ── Ollama ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}── Local LLM (Ollama) ──${RESET}"
prompt "OLLAMA_BASE_URL" \
    "Ollama Base URL" \
    "Where Ollama is running" \
    "http://localhost:11434"

prompt "OLLAMA_MODEL" \
    "Ollama Model" \
    "Local model for scoring and parsing" \
    "qwen2.5:7b"

# ── PostgreSQL ───────────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}── PostgreSQL ──${RESET}"
prompt "DATABASE_URL" \
    "Database URL" \
    "Full PostgreSQL connection string" \
    "postgresql://user:password@localhost:5432/jobhunter"

# ── Agent email ──────────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}── Agent Email (dedicated mailbox) ──${RESET}"
echo -e "${DIM}  This should be a dedicated address — NOT your personal email.${RESET}"

prompt "AGENT_EMAIL" \
    "Agent Email Address" \
    "The From address for job applications"

prompt "SMTP_HOST" \
    "SMTP Host" \
    "Your mail server hostname"

prompt "SMTP_PORT" \
    "SMTP Port" \
    "Usually 587 (STARTTLS) or 465 (SSL)" \
    "587"

prompt "SMTP_USER" \
    "SMTP Username" \
    "Usually the same as the email address"

prompt_secret "SMTP_PASS" \
    "SMTP Password" \
    "Email account password or app password"

prompt "SMTP_FROM_NAME" \
    "Display Name" \
    "Name shown in sent emails" \
    "Job Hunter"

# ── Document delivery ────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}── Document Delivery ──${RESET}"
echo -e "${DIM}  Your personal email — where documents are delivered to YOU.${RESET}"
echo -e "${DIM}  This is NOT the agent mailbox. Never used for anything else.${RESET}"
echo ""
prompt "PERSONAL_EMAIL" \
    "Your Personal Email Address" \
    "Where the agent sends finished CVs and cover letters"
echo ""

# ── Onboarding web form ──────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}── Onboarding web form ──${RESET}"
prompt "OPENCLAW_BASE_URL" \
    "OpenClaw Public Base URL" \
    "Public URL of your OpenClaw instance (e.g. https://openclaw.example.com) — used to send the /onboard link to the user"

prompt "ONBOARDING_PORT" \
    "Onboarding Server Port" \
    "Internal port for the onboarding Flask server (Caddy should proxy /onboard/* → this port)" \
    "8080"

# ── Note: Telegram is handled by setup_telegram.sh ──────────────────────────

echo ""
echo "────────────────────────────────────────"
echo "✓ .env saved to $ENV_FILE"
echo ""
echo "  Telegram will be configured in the next step."
echo ""