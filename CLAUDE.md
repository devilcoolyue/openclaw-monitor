# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

openclaw-monitor is a real-time web dashboard for monitoring OpenClaw sessions, logs, and token usage. It is a **zero-dependency** project: Python 3.10+ backend with a single-page HTML/CSS/JS frontend. No npm, pip, or build step required. Frontend uses native ES Modules; backend uses Python standard imports.

## Running the Server

```bash
# Default (port 18765, localhost)
python3 src/server.py

# Custom port
python3 src/server.py --port 9999

# Bind to Tailscale interface
python3 src/server.py --tailscale
```

Service management via CLI: `openclaw-monitor start|stop|restart|status|logs`

## Architecture

### Backend (`src/`) — 11 Python files

```
src/
  server.py          Entry point (~50 lines): _Server class, BIND_HOST, __main__
  config.py          Configuration: _parse_args(), _get_version(), _find_openclaw(), all constants/paths
  auth.py            Auth: _load_auth(), _verify_password(), _create_session(), _check_auth(), LOGIN_HTML
  cli_cache.py       CLI cache: _cli_cache, _run_cli_cached(), _cli_cache_worker(), get_cache(), start()
  diagnostics.py     Diagnostics: _file_diagnostics()
  tailscale.py       Tailscale: _get_tailscale_ip()
  handler.py         Handler class: do_GET/POST, all _api_* methods (read-only, no file modifications)
  sse.py             SSE utilities: _begin_sse(), _send_sse(), _json_resp(), _read_json_file()
  logs.py            Logs: _resolve_today_log(), _tail_log_file(), _parse_log_line(), _classify()
  sessions.py        Sessions: _find_session_file(), _scan_session_files(), _extract_session_info()
  jsonl.py           JSONL parsing: _parse_jsonl_line()
```

**Dependency graph** (no cycles):
- Leaf modules (no project imports): `config`, `sse`, `jsonl`, `tailscale`
- `auth` → config
- `cli_cache` → config
- `logs` → config, sse
- `sessions` → config
- `diagnostics` → config, sse
- `handler` → all other modules
- `server` → config, tailscale, cli_cache, handler

Modules use absolute imports (e.g. `import config`). `server.py` adds `src/` to `sys.path`.

### Frontend — HTML + 9 CSS + 16 JS files

```
public/
  index.html              HTML structure only (~180 lines)
  css/
    base.css              Variables, reset, scrollbar, icons, button animations
    sidebar.css           Sidebar, navigation, session cards, footer
    boot.css              Boot detection overlay
    toast.css             Toast notifications
    main.css              Main content area, toolbar, search, filters
    session.css           Session summary bar
    stream.css            Log rows, session blocks, markdown, JSON highlight
    system.css            System dashboard cards
    mobile.css            Responsive overrides (must load last)
  js/
    state.js              Global state object `S`
    i18n.js               I18N dict, KEY_ZH, i18n(), translateKey()
    utils.js              esc(), fmtTime(), fmtTokens(), renderMd(), hlJson(), BADGE_LABELS
    toast.js              showToast()
    mobile.js             isMobile(), openSidebar(), closeSidebar()
    theme.js              initTheme(), toggleTheme(), applyTheme()
    lang.js               initLang(), toggleLang(), applyLang(), updateAllText()
    boot.js               bootCheck(), setBootStep(), sleep()
    connection.js          closeES(), clearStream(), setConn(), pollHealth(), updateLiveTag()
    filter.js             filterMatch(), reRenderLive(), searchMatch()
    sse.js                startLive(), startSession()
    sessions.js           loadSessions(), renderSessions(), switchView()
    render-log.js         ensureLogHeader(), appendLogRow()
    render-session.js     appendSessionBlock()
    render-system.js      loadSystem(), renderSystem() and all render* helpers
    main.js               Entry point: DOMContentLoaded → init + bindAll + bootCheck
```

**ES Module notes**: Functions referenced via inline `onclick` are registered on `window` in `main.js`: `switchView`, `bootCheck`, `loadSystem`. Entry: `<script type="module" src="/js/main.js">`.

### Backend Request Flow

`Handler` class (in `handler.py`) routes requests through `do_GET` and `do_POST`. The dashboard is **read-only** — it only displays data, never modifies or deletes session files. Auth is cookie-based (`monitor_sid`, HttpOnly, SameSite=Strict). Password stored as `salt:sha256_hash` in `.auth` file.

Key API endpoints:
- `GET /api/sessions` — List sessions with token usage/cost metadata
- `GET /api/logs/stream` — SSE real-time log tail (max 2 concurrent, 50 lines/sec rate limit)
- `GET /api/session/<id>/stream` — SSE session event stream (history replay + live)
- `GET /api/system` — System diagnostics

### Data Sources

- **Sessions**: Parsed from JSONL files at `~/.openclaw/agents/main/sessions/*.jsonl`
- **Logs**: Tailed from `/tmp/openclaw/openclaw-YYYY-MM-DD.log` via subprocess
- **CLI cache**: Background thread refreshes `openclaw status --json` every 120s

### Concurrency Controls

- `MAX_LOG_STREAMS = 2` with `threading.Lock` gating (in `config.py`, modified by `handler.py`)
- `MAX_LOG_LINES_SEC = 50` rate limiting on SSE streams
- Thread-safe shared state for CLI cache and stream counters

## Scripts

- `scripts/install.sh` — Interactive install with password setup + systemd service
- `scripts/start.sh` — Start via systemd or fallback to direct execution
- `scripts/check.sh` — Health check with auto-restart
- `scripts/update.sh` — Git pull + service restart
- `scripts/uninstall.sh` — Clean removal
- `bin/openclaw-monitor` — Global CLI wrapper

## Key Conventions

- Python internal functions use `_underscore_prefix`
- Request logging is disabled (`log_message` is a no-op) for clean output
- Graceful fallbacks everywhere: CLI unavailable → direct JSONL scan; today's log missing → newest log file; systemd missing → PID-based management
- Session info extraction parses JSONL protocol messages into `{role, blocks[], meta}` format with per-model token/cost breakdown
- Frontend uses inline SVG icons (no external icon libraries)
- Bilingual UI (English/Chinese) with dark/light theme toggle
