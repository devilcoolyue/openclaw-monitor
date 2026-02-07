# openclaw-monitor

A real-time web dashboard for monitoring [OpenClaw](https://github.com/anthropics/openclaw) sessions, logs, and token usage.

## Features

- **Session Management** — View all active/idle sessions with model info, token usage, and cost breakdown
- **Real-time Log Streaming** — SSE-based live log viewer with type classification and filtering
- **Session Detail View** — Inspect individual session messages including thinking blocks, tool calls, and tool results
- **Token & Cost Tracking** — Per-session and per-model token usage with cost estimation
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
- (Optional) Tailscale for private network binding

## Quick Start

```bash
git clone https://github.com/<your-username>/openclaw-monitor.git
cd openclaw-monitor

# Install — set admin password
./scripts/install.sh

# Start the monitor server (default port: 10100)
./scripts/start.sh

# Or run directly with a custom port
python3 src/server.py --port 8888
```

Open `http://localhost:10100` in your browser. If a password was set during install, you'll see a login page.

## Installation

Run the install script to set an admin password:

```bash
./scripts/install.sh
```

This will:
1. Prompt for an admin password (hidden input)
2. Generate a salted SHA-256 hash and save it to `.auth`
3. Make `scripts/start.sh` and `scripts/check.sh` executable

If you skip installation or delete `.auth`, the dashboard runs without authentication (open access).

## Usage

### Start / Stop

```bash
# Start (background, with PID tracking)
./scripts/start.sh

# Start with Tailscale binding (private network only)
./scripts/start.sh --tailscale

# Check if running (suitable for crontab)
./scripts/check.sh

# Stop
kill $(cat monitor.pid)
```

### Tailscale Binding

Use the `--tailscale` flag to bind the server to your Tailscale IP instead of `0.0.0.0`:

```bash
./scripts/start.sh --tailscale
# or directly:
python3 src/server.py --port 8888 --tailscale
```

This makes the dashboard accessible only through your Tailscale network. Requires Tailscale to be installed and running.

### Auto-restart with crontab

```bash
# Check every minute, restart if not running
* * * * * /path/to/openclaw-monitor/scripts/check.sh
```

## Architecture

```
openclaw-monitor/
├── src/
│   └── server.py          # Python HTTP server with REST API + SSE endpoints + auth
├── public/
│   └── index.html         # Single-page dashboard (HTML + CSS + JS)
├── scripts/
│   ├── install.sh         # Installation script (password setup)
│   ├── start.sh           # Startup script with PID management
│   └── check.sh           # Health check script for crontab
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
2. Calls `openclaw` CLI for session listing and log streaming
3. Falls back to direct file scanning when CLI is unavailable
4. Serves a single-page dashboard via built-in HTTP server
5. Uses Server-Sent Events (SSE) for real-time updates

## License

MIT
