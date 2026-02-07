#!/bin/bash
# openclaw-monitor installation script
# Supports both local and remote (curl | bash) installation
#
# Remote:  curl -fsSL https://raw.githubusercontent.com/devilcoolyue/openclaw-monitor/main/scripts/install.sh | bash
# Local:   ./scripts/install.sh

set -e

REPO_URL="https://github.com/devilcoolyue/openclaw-monitor.git"
INSTALL_DIR="${OPENCLAW_MONITOR_DIR:-$HOME/openclaw-monitor}"
PORT="${OPENCLAW_MONITOR_PORT:-18765}"
SERVICE_NAME="openclaw-monitor"

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
echo "  Port:     $PORT"
echo ""

# ── Password setup ────────────────────────────────────────
if [ -f "$AUTH_FILE" ]; then
    echo "  Existing password found, keeping it."
    echo "  (To reset, delete .auth and re-run install.sh)"
    echo ""
else
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
fi

# Make scripts executable
chmod +x scripts/start.sh scripts/check.sh scripts/install.sh scripts/update.sh scripts/uninstall.sh bin/openclaw-monitor 2>/dev/null || true

# ── Install systemd user service ──────────────────────────────
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SYSTEMD_USER_DIR/${SERVICE_NAME}.service"

mkdir -p "$SYSTEMD_USER_DIR"

# Detect extra args for Tailscale
EXTRA_ARGS=""
for arg in "$@"; do
    case "$arg" in
        --tailscale) EXTRA_ARGS="$EXTRA_ARGS --tailscale" ;;
    esac
done

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=openclaw Monitor Dashboard
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$(command -v python3) $PROJECT_DIR/src/server.py --port $PORT $EXTRA_ARGS
Restart=on-failure
RestartSec=5
StandardOutput=append:$PROJECT_DIR/monitor.log
StandardError=append:$PROJECT_DIR/monitor.log

[Install]
WantedBy=default.target
EOF

# Reload systemd user daemon
systemctl --user daemon-reload

# Enable and start the service
systemctl --user enable --now "$SERVICE_NAME" 2>/dev/null

# Enable lingering so user services survive logout
loginctl enable-linger "$(whoami)" 2>/dev/null || true

# ── Install CLI symlink ───────────────────────────────────
CLI_DIR="$HOME/.local/bin"
CLI_LINK="$CLI_DIR/openclaw-monitor"
mkdir -p "$CLI_DIR"
ln -sf "$PROJECT_DIR/bin/openclaw-monitor" "$CLI_LINK"

echo ""
echo "  ✓ Password configured"
echo "  ✓ Scripts made executable"
echo "  ✓ Systemd user service installed"
echo "  ✓ CLI installed to $CLI_LINK"

# Check if ~/.local/bin is in PATH
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$CLI_DIR"; then
    echo ""
    echo "  ⚠ $CLI_DIR is not in your PATH."
    echo "  Add it by running:"
    echo "    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
fi

echo ""
echo "  Manage the service:"
echo "    openclaw-monitor start       # Start"
echo "    openclaw-monitor stop        # Stop"
echo "    openclaw-monitor restart     # Restart"
echo "    openclaw-monitor status      # Status & health check"
echo "    openclaw-monitor logs        # View logs"
echo "    openclaw-monitor update      # Pull latest & restart"
echo "    openclaw-monitor uninstall   # Remove everything"
echo "    openclaw-monitor version     # Show version"
echo ""
