#!/bin/bash
# openclaw-monitor update script
# Usage: ./scripts/update.sh

set -e

SERVICE_NAME="openclaw-monitor"

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

cd "$PROJECT_DIR"

echo ""
echo "  openclaw-monitor — Update"
echo "  ─────────────────────────"
echo ""

# ── Check git is available ────────────────────────────────
if ! command -v git &>/dev/null; then
    echo "  ERROR: git is required but not installed."
    exit 1
fi

if [ ! -d ".git" ]; then
    echo "  ERROR: Not a git repository. Cannot update."
    exit 1
fi

# ── Current version ───────────────────────────────────────
CURRENT=$(git log -1 --format='%h (%ci)' 2>/dev/null | sed 's/ [+-][0-9]*$//')
echo "  Current version : $CURRENT"

# ── Ensure sparse checkout is configured ──────────────────
# If this is a full clone, set up sparse checkout to skip large assets on future pulls
if ! git sparse-checkout list &>/dev/null || [ "$(git config core.sparseCheckout)" != "true" ]; then
    if [ -d "image" ] || [ -d "openclaw-env-install" ]; then
        echo "  Optimizing: enabling sparse checkout to skip large assets..."
        git sparse-checkout init --cone
        git sparse-checkout set src public scripts bin \
            CLAUDE.md LICENSE README.md README.en.md .gitignore
    fi
fi

# ── Fetch remote ──────────────────────────────────────────
echo "  Fetching updates..."
git fetch origin 2>/dev/null

# ── Compare local vs remote ───────────────────────────────
LOCAL=$(git rev-parse HEAD 2>/dev/null)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
REMOTE=$(git rev-parse "origin/$BRANCH" 2>/dev/null || echo "")

if [ -z "$REMOTE" ]; then
    echo "  ERROR: Cannot find remote branch origin/$BRANCH."
    exit 1
fi

if [ "$LOCAL" = "$REMOTE" ]; then
    echo ""
    echo "  Already up to date."
    echo ""
    exit 0
fi

# ── Show pending changes ──────────────────────────────────
COMMITS_BEHIND=$(git rev-list --count HEAD..origin/$BRANCH 2>/dev/null)
echo "  $COMMITS_BEHIND new commit(s) available"
echo ""
git --no-pager log --oneline HEAD..origin/$BRANCH 2>/dev/null | sed 's/^/    /'
echo ""

# ── Pull changes ──────────────────────────────────────────
echo "  Pulling changes..."
if ! git pull --ff-only 2>/dev/null; then
    echo ""
    echo "  ERROR: Fast-forward merge failed."
    echo "  Your local branch has diverged from origin/$BRANCH."
    echo "  Resolve manually with: git pull --rebase"
    exit 1
fi

# ── Make new scripts executable ───────────────────────────
chmod +x scripts/start.sh scripts/check.sh scripts/install.sh scripts/update.sh scripts/uninstall.sh bin/openclaw-monitor 2>/dev/null || true

# ── Install CLI symlink if missing ───────────────────────
CLI_DIR="$HOME/.local/bin"
CLI_LINK="$CLI_DIR/openclaw-monitor"
if [ ! -L "$CLI_LINK" ] && [ -f "$PROJECT_DIR/bin/openclaw-monitor" ]; then
    mkdir -p "$CLI_DIR"
    ln -sf "$PROJECT_DIR/bin/openclaw-monitor" "$CLI_LINK"
    echo "  CLI installed to $CLI_LINK"

    if ! echo "$PATH" | tr ':' '\n' | grep -qx "$CLI_DIR"; then
        echo ""
        echo "  ⚠ $CLI_DIR is not in your PATH."
        echo "  Add it by running:"
        echo "    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
    fi
fi

# ── Restart service ───────────────────────────────────────
echo "  Restarting service..."
if systemctl --user restart "$SERVICE_NAME" 2>/dev/null; then
    echo "  Service restarted."
else
    echo "  WARNING: Could not restart systemd service."
    echo "  You may need to restart manually."
fi

# ── Show result ───────────────────────────────────────────
UPDATED=$(git log -1 --format='%h (%ci)' 2>/dev/null | sed 's/ [+-][0-9]*$//')
echo ""
echo "  Updated: $CURRENT"
echo "       ->  $UPDATED"
echo ""
echo "  Tip: You can now manage the service with:"
echo "    openclaw-monitor help"
echo ""
