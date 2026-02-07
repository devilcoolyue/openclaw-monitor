# openclaw-monitor

A real-time web dashboard for monitoring [OpenClaw](https://github.com/anthropics/openclaw) sessions, logs, and token usage.

## Features

- **Session Management** — View all active/idle sessions with model info, token usage, and cost breakdown
- **Real-time Log Streaming** — Direct file tail with SSE push, no gateway RPC overhead
- **Session Detail View** — Inspect individual session messages including thinking blocks, tool calls, and tool results
- **Token & Cost Tracking** — Per-session and per-model token usage with cost estimation
- **Concurrency & Rate Limiting** — Max 2 concurrent log streams, 50 lines/sec throttle to prevent server overload
- **Login Authentication** — Password-protected access with secure session cookies
- **Tailscale Support** — Optionally bind to Tailscale interface for private network access
- **Dark / Light Theme** — Toggle between dark and light mode
- **Auto Refresh** — Session list auto-refreshes; log stream stays connected via SSE
- **Session Cleanup** — Delete old sessions directly from the dashboard
- **Zero Dependencies** — Pure Python backend + vanilla HTML/CSS/JS frontend, no npm or pip install needed

## Screenshot

<!-- TODO: add screenshot -->

## Requirements

- Python 3.10+
- OpenClaw CLI installed and accessible in `$PATH`
- systemd (for user service management)
- (Optional) Tailscale for private network binding

## Quick Start

One-liner install on a fresh server:

```bash
curl -fsSL https://raw.githubusercontent.com/devilcoolyue/openclaw-monitor/main/scripts/install.sh | bash
```

This will clone the repo to `~/openclaw-monitor`, prompt for an admin password, and install a systemd user service.

To install to a custom directory:

```bash
OPENCLAW_MONITOR_DIR=~/my-monitor curl -fsSL https://raw.githubusercontent.com/devilcoolyue/openclaw-monitor/main/scripts/install.sh | bash
```

To use a custom port (default: 18765):

```bash
OPENCLAW_MONITOR_PORT=9999 curl -fsSL https://raw.githubusercontent.com/devilcoolyue/openclaw-monitor/main/scripts/install.sh | bash
```

Then start the service:

```bash
systemctl --user start openclaw-monitor
```

Open `http://<server-ip>:18765` in your browser.

## Manual Installation

```bash
git clone https://github.com/devilcoolyue/openclaw-monitor.git ~/openclaw-monitor
cd ~/openclaw-monitor

# Set admin password and install systemd service
./scripts/install.sh

# Start the service (default port: 18765)
systemctl --user start openclaw-monitor

# Or run directly with a custom port
python3 src/server.py --port 9999
```

If you skip installation or delete `.auth`, the dashboard runs without authentication (open access).

## Usage

### Service Management

```bash
# Start
systemctl --user start openclaw-monitor

# Stop
systemctl --user stop openclaw-monitor

# Restart
systemctl --user restart openclaw-monitor

# Status & health check
systemctl --user status openclaw-monitor

# View logs
journalctl --user -u openclaw-monitor -f

# Enable auto-start on login
systemctl --user enable openclaw-monitor

# Disable auto-start
systemctl --user disable openclaw-monitor
```

Or use the helper scripts:

```bash
# Start (delegates to systemctl if service is installed)
./scripts/start.sh

# Health check
./scripts/check.sh
```

### Tailscale Binding

Use the `--tailscale` flag during installation to bind the server to your Tailscale IP:

```bash
./scripts/install.sh --tailscale
```

Or run directly:

```bash
python3 src/server.py --port 18765 --tailscale
```

This makes the dashboard accessible only through your Tailscale network. Requires Tailscale to be installed and running.

## Architecture

```
openclaw-monitor/
├── src/
│   └── server.py          # Python HTTP server with REST API + SSE endpoints + auth
├── public/
│   └── index.html         # Single-page dashboard (HTML + CSS + JS)
├── scripts/
│   ├── install.sh         # Installation script (password setup + systemd service)
│   ├── start.sh           # Startup helper (delegates to systemctl)
│   └── check.sh           # Health check script (delegates to systemctl)
├── .gitignore
├── LICENSE
└── README.md
```

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/sessions` | GET | List all sessions with metadata and usage |
| `/api/health` | GET | Check OpenClaw availability and environment |
| `/api/logs/stream` | GET (SSE) | Real-time log stream |
| `/api/session/<id>/stream` | GET (SSE) | Session event stream (history + live tail) |
| `/api/session/<id>` | DELETE | Delete a session file |
| `/api/login` | POST | Authenticate with password |
| `/api/logout` | GET | Clear session and log out |

All endpoints except `/api/login` and `/api/logout` require authentication when `.auth` is present.

### Security

- Password stored as SHA-256 hash with random 32-byte salt
- Session tokens: 64-char hex via `secrets.token_hex(32)`
- Cookie flags: `HttpOnly`, `SameSite=Strict`
- Session TTL: 7 days
- Login page is self-contained (no dashboard data exposed)
- Without `.auth` file, auth is disabled (backwards compatible)

### How It Works

1. Reads session data from `~/.openclaw/agents/main/sessions/*.jsonl`
2. Calls `openclaw` CLI for session listing; falls back to direct file scanning when CLI is unavailable
3. Streams logs by directly tailing `/tmp/openclaw/openclaw-YYYY-MM-DD.log` (bypasses gateway RPC for minimal resource usage)
4. Enforces concurrency limits (max 2 SSE streams) and rate limiting (50 lines/sec) to protect low-memory servers
5. Serves a single-page dashboard via built-in HTTP server
6. Uses Server-Sent Events (SSE) for real-time updates
7. Managed as a systemd user service for reliable startup and auto-restart

## License

MIT
