#!/usr/bin/env bash
# install/check_prereqs.sh — Check all prerequisites before installing
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

echo "Checking prerequisites:"

check "Node.js 22+"    "node -e 'process.exit(parseInt(process.version.slice(1)) >= 22 ? 0 : 1)'" \
    "Install from https://nodejs.org — need v22 or higher"

check "Python 3.10+"  "python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'" \
    "Install Python 3.10+ from https://python.org"

check "pip"           "pip --version" \
    "pip is required — install via your package manager"

check "OpenClaw"      "openclaw --version" \
    "Install OpenClaw: npm install -g openclaw@latest"

check "Ollama"        "curl -sf http://localhost:11434/api/tags" \
    "Install Ollama from https://ollama.ai and start it: ollama serve"

check "PostgreSQL"    "psql --version" \
    "Install PostgreSQL client: apt install postgresql-client"

check "git"           "git --version" \
    "Install git: apt install git"

if [ "$FAIL" -eq 1 ]; then
    echo ""
    echo "Please fix the issues above and re-run the installer."
    exit 1
fi
