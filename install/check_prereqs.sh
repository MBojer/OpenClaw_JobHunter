#!/usr/bin/env bash
# install/check_prereqs.sh — Check prerequisites before installing
set -euo pipefail

FAIL=0

check() {
    local name="$1" cmd="$2" hint="$3"
    if eval "$cmd" &>/dev/null; then
        echo "  ✓ $name"
    else
        echo "  ✗ $name — $hint"
        FAIL=1
    fi
}

warn_only() {
    local name="$1" cmd="$2" hint="$3"
    if eval "$cmd" &>/dev/null; then
        echo "  ✓ $name"
    else
        echo "  ⚠  $name — $hint"
        # Not a hard failure — connectivity confirmed later after .env is set up
    fi
}

echo "Checking prerequisites:"

check "Node.js 22+" \
    "node -e 'process.exit(parseInt(process.version.slice(1)) >= 22 ? 0 : 1)'" \
    "Install from https://nodejs.org — need v22 or higher"

check "Python 3.10+" \
    "python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'" \
    "Install Python 3.10+ from https://python.org"

check "pip" \
    "pip --version" \
    "pip is required — install via your package manager"

check "OpenClaw" \
    "openclaw --version" \
    "Install OpenClaw: npm install -g openclaw@latest"

check "git" \
    "git --version" \
    "Install git: apt install git"

# ── Processing LLM — may be remote, read URL from .env if available ──────────
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
PROC_LLM_URL="http://localhost:11434"

if [ -f "$ENV_FILE" ]; then
    LOADED_URL=$(grep "^PROC_LLM_BASE_URL=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
    [ -n "$LOADED_URL" ] && PROC_LLM_URL="$LOADED_URL"
fi

warn_only "Processing LLM reachable at $PROC_LLM_URL" \
    "curl -sf ${PROC_LLM_URL}/api/tags" \
    "Processing LLM not reachable at $PROC_LLM_URL — set PROC_LLM_BASE_URL in .env"

# ── PostgreSQL — no local client needed, psycopg2 connects directly ──────────
# Connectivity is verified in install/verify.sh after DATABASE_URL is configured.
echo "  ✓ PostgreSQL (connectivity checked after .env setup)"

if [ "$FAIL" -eq 1 ]; then
    echo ""
    echo "Please fix the issues above and re-run the installer."
    exit 1
fi