#!/bin/bash
# openclaw-monitor installation script
# Sets admin password and makes scripts executable

set -e

cd "$(dirname "$0")/.."

AUTH_FILE=".auth"

echo ""
echo "  openclaw-monitor — Setup"
echo "  ────────────────────────"
echo ""

# Prompt for admin password
while true; do
    read -s -p "  Set admin password: " PASSWORD
    echo ""
    if [ -z "$PASSWORD" ]; then
        echo "  Password cannot be empty. Try again."
        continue
    fi
    read -s -p "  Confirm password:   " PASSWORD2
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
chmod +x scripts/start.sh scripts/check.sh 2>/dev/null || true

echo ""
echo "  ✓ Password saved to .auth"
echo "  ✓ Scripts made executable"
echo ""
echo "  Start the server:"
echo "    ./scripts/start.sh"
echo ""
echo "  Start with Tailscale binding:"
echo "    ./scripts/start.sh --tailscale"
echo ""
