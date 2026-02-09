#!/bin/bash
# openclaw-monitor uninstall script
# Usage: ./scripts/uninstall.sh

set -e

SERVICE_NAME="openclaw-monitor"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SYSTEMD_USER_DIR/${SERVICE_NAME}.service"

# ── Locate project directory ──────────────────────────────
if [ -f "src/server.py" ]; then
    PROJECT_DIR="$(pwd)"
elif [ -f "$(dirname "$0")/../src/server.py" ] 2>/dev/null; then
    PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
else
    echo "  ERROR: Cannot find openclaw-monitor project directory."
    echo "  Run this script from the project root or scripts/ directory."
    exit 1
fi

echo ""
echo "  openclaw-monitor — Uninstall"
echo "  ────────────────────────────"
echo "  Location: $PROJECT_DIR"
echo ""

# ── Confirm ───────────────────────────────────────────────
read -p "  Are you sure you want to uninstall? [y/N] " CONFIRM < /dev/tty
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "  Cancelled."
    exit 0
fi
echo ""

# ── Stop and disable systemd service ─────────────────────
if systemctl --user is-active "$SERVICE_NAME" &>/dev/null; then
    echo "  Stopping service..."
    systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
fi

if systemctl --user is-enabled "$SERVICE_NAME" &>/dev/null; then
    echo "  Disabling service..."
    systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
fi

if [ -f "$SERVICE_FILE" ]; then
    echo "  Removing service file..."
    rm -f "$SERVICE_FILE"
    systemctl --user daemon-reload 2>/dev/null || true
fi

echo "  Systemd service removed."

# ── Remove CLI symlink ────────────────────────────────────
CLI_LINK="$HOME/.local/bin/openclaw-monitor"
if [ -L "$CLI_LINK" ]; then
    rm -f "$CLI_LINK"
    echo "  CLI symlink removed."
fi

# ── Remove auth and log files ─────────────────────────────
# Unlock immutable attribute before removal
chattr -i "$PROJECT_DIR/.auth" 2>/dev/null || true
chattr -i "$PROJECT_DIR/.auth_required" 2>/dev/null || true
rm -f "$PROJECT_DIR/.auth" 2>/dev/null || true
rm -f "$PROJECT_DIR/.auth_required" 2>/dev/null || true
rm -f "$PROJECT_DIR/monitor.log" 2>/dev/null || true
echo "  Auth and log files removed."

# ── Optionally remove project directory ───────────────────
echo ""
read -p "  Also delete the project directory ($PROJECT_DIR)? [y/N] " DEL_DIR < /dev/tty
if [[ "$DEL_DIR" =~ ^[Yy]$ ]]; then
    rm -rf "$PROJECT_DIR"
    echo "  Project directory deleted."
else
    echo "  Project directory kept."
fi

echo ""
echo "  Uninstall complete."
echo ""
