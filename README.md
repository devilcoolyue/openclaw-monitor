# openclaw-monitor

A real-time web dashboard for monitoring [OpenClaw](https://github.com/anthropics/openclaw) sessions, logs, and token usage.

## Features

- **Session Management** — View all active/idle sessions with model info, token usage, and cost breakdown
- **Real-time Log Streaming** — SSE-based live log viewer with type classification and filtering
- **Session Detail View** — Inspect individual session messages including thinking blocks, tool calls, and tool results
- **Token & Cost Tracking** — Per-session and per-model token usage with cost estimation
- **Dark / Light Theme** — Toggle between dark and light mode
- **Auto Refresh** — Session list auto-refreshes; log stream stays connected via SSE
- **Session Cleanup** — Delete old sessions directly from the dashboard
- **Zero Dependencies** — Pure Python backend + vanilla HTML/CSS/JS frontend, no npm or pip install needed

## Screenshot

<!-- TODO: add screenshot -->

## Requirements

- Python 3.10+
- OpenClaw CLI installed and accessible in `$PATH`

## Quick Start

```bash
git clone https://github.com/<your-username>/openclaw-monitor.git
cd openclaw-monitor

# Start the monitor server (default port: 10100)
./start.sh

# Or run directly with a custom port
python3 server.py --port 8888
```

Open `http://localhost:10100` in your browser.

## Usage

### Start / Stop

```bash
# Start (background, with PID tracking)
./start.sh

# Check if running (suitable for crontab)
./check.sh

# Stop
kill $(cat monitor.pid)
```

### Auto-restart with crontab

```bash
# Check every minute, restart if not running
* * * * * /path/to/openclaw-monitor/check.sh
```

## Architecture

```
openclaw-monitor/
├── server.py      # Python HTTP server with REST API + SSE endpoints
├── index.html     # Single-page dashboard (HTML + CSS + JS)
├── start.sh       # Startup script with PID management
└── check.sh       # Health check script for crontab
```

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/sessions` | GET | List all sessions with metadata and usage |
| `/api/health` | GET | Check OpenClaw availability and environment |
| `/api/logs/stream` | GET (SSE) | Real-time log stream |
| `/api/session/<id>/stream` | GET (SSE) | Session event stream (history + live tail) |
| `/api/session/<id>` | DELETE | Delete a session file |

### How It Works

1. Reads session data from `~/.openclaw/agents/main/sessions/*.jsonl`
2. Calls `openclaw` CLI for session listing and log streaming
3. Falls back to direct file scanning when CLI is unavailable
4. Serves a single-page dashboard via built-in HTTP server
5. Uses Server-Sent Events (SSE) for real-time updates

## License

MIT
