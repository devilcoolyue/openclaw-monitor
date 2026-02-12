# Repository Guidelines

## Project Structure & Module Organization
- `src/`: Python backend (HTTP handler, auth, SSE, session/log parsing, CLI cache).
- `public/`: Frontend SPA assets.
- `public/js/`: ES module UI logic (`render-system.js`, `sessions.js`, `connection.js`, etc.).
- `public/css/`: Component and page styles.
- `scripts/`: Operational scripts (`install.sh`, `start.sh`, `check.sh`, `update.sh`, `uninstall.sh`).
- `bin/`: Shell entrypoints/helpers.
- Runtime/auth artifacts such as `.auth`, `.auth_required`, and `monitor.log` are local operational files.

## Build, Test, and Development Commands
- No build step (zero-dependency project).
- Run locally: `python3 src/server.py --port 18765`
- Run with Tailscale bind: `python3 src/server.py --port 18765 --tailscale`
- Install service + auth setup: `./scripts/install.sh`
- Service control: `systemctl --user start|stop|restart|status openclaw-monitor`
- Maintenance helpers:
- `./scripts/check.sh` (health check + auto-restart)
- `./scripts/update.sh` (git pull + restart)

## Coding Style & Naming Conventions
- Python: 4-space indentation, standard library first, internal helpers use leading underscore (for example `_api_system`, `_run_cli_cached`).
- JavaScript: vanilla ES modules, 2-space indentation, keep rendering logic grouped by page/feature.
- Naming:
- Python files/functions: `snake_case`
- Frontend module files: kebab-style (for example `render-system.js`)
- Keep changes focused; avoid unrelated refactors in operational scripts.

## Testing Guidelines
- No dedicated automated test suite is currently included.
- Validate changes with targeted manual checks:
- API smoke tests (for example `curl http://127.0.0.1:18765/api/version` and authenticated `/api/system`).
- UI checks in Session and System pages after edits.
- If you add parsing logic, test both normal JSON and noisy CLI output cases.

## Commit & Pull Request Guidelines
- Follow concise, imperative commit subjects. Existing history uses styles like:
- `Fix: ...`
- `chore: ...`
- Keep one logical change per commit when possible.
- PRs should include:
- What changed and why
- Risk/rollback notes for service-impacting edits
- Manual verification steps
- Screenshots/GIFs for frontend behavior changes

## Security & Configuration Tips
- Never commit real credentials or auth secrets.
- Treat `.auth` and `.auth_required` as sensitive operational files.
- Prefer user service management (`systemctl --user`) over ad-hoc background processes for persistence.
