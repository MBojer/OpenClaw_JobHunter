#!/usr/bin/env bash
# JobHunter v2 — Installer
# The repo IS the OpenClaw workspace — clone directly to workspace path.
# Usage: curl -fsSL https://raw.githubusercontent.com/MBojer/OpenClaw_JobHunter/main/install.sh | bash
# Or:    ./install.sh  (from within a cloned copy)
set -euo pipefail

REPO_URL="https://github.com/MBojer/OpenClaw_JobHunter.git"
WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace-jobhunter}"

BOLD="\033[1m"; RESET="\033[0m"; GREEN="\033[32m"; RED="\033[31m"; YELLOW="\033[33m"

info()    { echo -e "${BOLD}→${RESET} $*"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET}  $*"; }
error()   { echo -e "${RED}✗${RESET} $*"; exit 1; }

echo ""
echo -e "${BOLD}╔══════════════════════════════╗${RESET}"
echo -e "${BOLD}║   JobHunter v2 Installer 🦞   ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════╝${RESET}"
echo ""

# ── Step 1: Prerequisites ────────────────────────────────────────────────────
info "Checking prerequisites..."
bash "$(dirname "$0")/install/check_prereqs.sh" || error "Prerequisites check failed."
success "Prerequisites OK"

# ── Step 2: Clone repo directly into OpenClaw workspace ─────────────────────
if [ -d "$WORKSPACE/.git" ]; then
    info "Existing install found at $WORKSPACE — pulling latest..."
    git -C "$WORKSPACE" pull --ff-only
    success "Repository updated"
else
    if [ -d "$WORKSPACE" ] && [ "$(ls -A $WORKSPACE)" ]; then
        warn "Workspace directory exists but is not a git repo: $WORKSPACE"
        read -rp "  Overwrite? This will remove existing workspace files. [y/N]: " confirm
        [[ "$confirm" =~ ^[Yy]$ ]] || error "Aborted."
        rm -rf "$WORKSPACE"
    fi
    info "Cloning repository into workspace: $WORKSPACE"
    git clone "$REPO_URL" "$WORKSPACE"
    success "Repository cloned → $WORKSPACE"
fi

cd "$WORKSPACE"

# ── Step 3: Python dependencies ─────────────────────────────────────────────
info "Installing Python dependencies..."
pip install -r requirements.txt --break-system-packages -q
success "Python dependencies installed"

# ── Step 4: Environment setup ───────────────────────────────────────────────
if [ ! -f .env ]; then
    info "Setting up environment (.env)..."
    bash install/setup_env.sh
else
    warn ".env already exists — skipping. Edit manually if needed: $WORKSPACE/.env"
fi

# ── Step 5: Database migrations ─────────────────────────────────────────────
info "Running database migrations..."
python3 scripts/db/migrate.py
success "Database ready"

# ── Step 6: Ollama model ────────────────────────────────────────────────────
source .env
MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
info "Checking Ollama model ($MODEL)..."
if python3 -c "
import sys
sys.path.insert(0, '.')
from scripts.local_llm.ollama_client import model_is_pulled
sys.exit(0 if model_is_pulled() else 1)
" 2>/dev/null; then
    success "$MODEL already pulled"
else
    warn "$MODEL not found — pulling now (~4.5GB, this may take a while)..."
    ollama pull "$MODEL"
    success "$MODEL pulled"
fi

# ── Step 7: Register agent with OpenClaw ────────────────────────────────────
# Repo IS the workspace — just register the agent pointing at it
info "Registering JobHunter agent with OpenClaw..."
AGENT_MODEL="${OPENROUTER_MODEL:-openrouter/stepfun/step-3.5-flash:free}"

if openclaw agents list --json 2>/dev/null | grep -q '"jobhunter"'; then
    warn "Agent 'jobhunter' already registered — skipping."
else
    openclaw agents add jobhunter \
        --workspace "$WORKSPACE" \
        --model "$AGENT_MODEL" \
        --non-interactive \
        --json
    success "Agent 'jobhunter' registered with workspace: $WORKSPACE"
fi

# ── Step 8: Telegram setup ──────────────────────────────────────────────────
info "Setting up Telegram..."
bash install/setup_telegram.sh
success "Telegram configured"

# ── Step 9: Health check ───────────────────────────────────────────────────
info "Running health check..."
bash install/verify.sh

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔════════════════════════════════════╗${RESET}"
echo -e "${GREEN}${BOLD}║   JobHunter v2 installed! 🦞        ║${RESET}"
echo -e "${GREEN}${BOLD}╚════════════════════════════════════╝${RESET}"
echo ""
echo "  Workspace: $WORKSPACE"
echo "  (This is your git repo — update anytime with: cd $WORKSPACE && git pull)"
echo ""
echo "  Next steps:"
echo "  1. Start the gateway:       openclaw gateway"
echo "  2. Register cron jobs:      python3 install/setup_cron.py"
echo "  3. Message your bot:        /start"
echo "  4. Paste your LinkedIn profile when prompted"
echo ""