#!/bin/bash
# openclaw-monitor installation script
# Supports both local and remote (curl | bash) installation
#
# Remote:  curl -fsSL https://raw.githubusercontent.com/devilcoolyue/openclaw-monitor/main/scripts/install.sh | bash
# Local:   ./scripts/install.sh

set -e

REPO_URL="https://github.com/devilcoolyue/openclaw-monitor.git"
INSTALL_DIR="${OPENCLAW_MONITOR_DIR:-/opt/openclaw-monitor}"

# ── Detect if running inside the repo or via curl pipe ────────
if [ -f "src/server.py" ]; then
    # Already inside the project directory
    PROJECT_DIR="$(pwd)"
elif [ -f "$(dirname "$0")/../src/server.py" ] 2>/dev/null; then
    # Running from scripts/ subdirectory
    PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
else
    # Remote install — clone the repo
    echo ""
    echo "  openclaw-monitor — Remote Install"
    echo "  ──────────────────────────────────"
    echo ""

    if ! command -v git &>/dev/null; then
        echo "  ERROR: git is required but not installed."
        exit 1
    fi
    if ! command -v python3 &>/dev/null; then
        echo "  ERROR: python3 is required but not installed."
        exit 1
    fi

    if [ -d "$INSTALL_DIR/.git" ]; then
        echo "  Updating existing installation at $INSTALL_DIR ..."
        git -C "$INSTALL_DIR" pull --ff-only
    else
        echo "  Cloning to $INSTALL_DIR ..."
        mkdir -p "$(dirname "$INSTALL_DIR")"
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi

    PROJECT_DIR="$INSTALL_DIR"
    echo ""
fi

cd "$PROJECT_DIR"

AUTH_FILE=".auth"

echo ""
echo "  openclaw-monitor — Setup"
echo "  ────────────────────────"
echo "  Location: $PROJECT_DIR"
echo ""

# Prompt for admin password
# Use /dev/tty so it works when piped from curl
while true; do
    read -s -p "  Set admin password: " PASSWORD < /dev/tty
    echo ""
    if [ -z "$PASSWORD" ]; then
        echo "  Password cannot be empty. Try again."
        continue
    fi
    read -s -p "  Confirm password:   " PASSWORD2 < /dev/tty
    echo ""
    if [ "$PASSWORD" = "$PASSWORD2" ]; then
        break
    fi
    echo "  Passwords do not match. Try again."
    echo ""
done

# Generate salt + SHA-256 hash using Python stdlib
# Pass password via stdin to avoid shell escaping issues
AUTH_ENTRY=$(printf '%s' "$PASSWORD" | python3 -c "
import hashlib, secrets, sys
password = sys.stdin.read()
salt = secrets.token_hex(32)
h = hashlib.sha256((salt + password).encode()).hexdigest()
print(salt + ':' + h)
")

echo "$AUTH_ENTRY" > "$AUTH_FILE"
chmod 600 "$AUTH_FILE"

# Make scripts executable
chmod +x scripts/start.sh scripts/check.sh scripts/install.sh 2>/dev/null || true

echo ""
echo "  ✓ Password saved to .auth"
echo "  ✓ Scripts made executable"
echo ""
echo "  Start the server:"
echo "    cd $PROJECT_DIR && ./scripts/start.sh"
echo ""
echo "  Start with Tailscale binding:"
echo "    cd $PROJECT_DIR && ./scripts/start.sh --tailscale"
echo ""
echo "  Auto-restart (add to crontab):"
echo "    * * * * * $PROJECT_DIR/scripts/check.sh"
echo ""
