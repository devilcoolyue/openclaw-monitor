"""
Configuration, constants, paths, CLI arguments, and version detection.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime

# ── CLI Arguments ────────────────────────────────────────────
def _parse_args():
    p = argparse.ArgumentParser(description='openclaw Monitor server')
    p.add_argument('--port', type=int, default=18765, help='Port to listen on (default: 18765)')
    p.add_argument('--tailscale', action='store_true', help='Bind to Tailscale IP instead of 0.0.0.0')
    p.add_argument('--version', action='store_true', help='Print version and exit')
    return p.parse_args()

ARGS        = _parse_args()
PORT        = ARGS.port
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVE_DIR   = os.path.join(BASE_DIR, 'public')

# ── Version ──────────────────────────────────────────────────
def _get_version():
    """Read version from git: short hash + commit date."""
    try:
        r = subprocess.run(
            ['git', 'log', '-1', '--format=%h %ci'],
            capture_output=True, text=True, timeout=5, cwd=BASE_DIR)
        if r.returncode == 0 and r.stdout.strip():
            parts = r.stdout.strip().split()
            h = parts[0]
            date = parts[1] if len(parts) > 1 else ''
            return {'hash': h, 'date': date, 'version': f'{h} ({date})'}
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return {'hash': 'unknown', 'date': '', 'version': 'unknown'}

if ARGS.version:
    print(_get_version()['version'])
    sys.exit(0)

# ── Paths ────────────────────────────────────────────────────
SESSION_DIR = os.path.expanduser("~/.openclaw/agents/main/sessions")
LOG_DIR     = "/tmp/openclaw"
TODAY_LOG   = os.path.join(LOG_DIR, f"openclaw-{datetime.now().strftime('%Y-%m-%d')}.log")

# ── System monitoring paths ─────────────────────────────────
OC_ROOT         = os.path.expanduser("~/.openclaw")
SESSIONS_JSON   = os.path.join(SESSION_DIR, "sessions.json")
DEVICES_PAIRED  = os.path.join(OC_ROOT, "devices", "paired.json")
DEVICES_PENDING = os.path.join(OC_ROOT, "devices", "pending.json")
CRON_JOBS       = os.path.join(OC_ROOT, "cron", "jobs.json")
UPDATE_CHECK    = os.path.join(OC_ROOT, "update-check.json")
EXEC_APPROVALS  = os.path.join(OC_ROOT, "exec-approvals.json")

# ── Regex patterns ───────────────────────────────────────────
UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)
TS_RE   = re.compile(r'^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?|\d{2}:\d{2}:\d{2}(?:\.\d+)?)')

# ── SSE concurrency & rate limiting ─────────────────────────
MAX_LOG_STREAMS     = 2
MAX_LOG_LINES_SEC   = 50
_log_stream_count   = 0
_log_stream_lock    = threading.Lock()

MAX_SESSION_STREAMS   = 3
_session_stream_count = 0
_session_stream_lock  = threading.Lock()

# ── Auth config ─────────────────────────────────────────────
AUTH_FILE     = os.path.join(BASE_DIR, '.auth')
SESSION_TTL   = 7 * 24 * 3600  # 7 days
COOKIE_NAME   = 'monitor_sid'

# ── Resolve openclaw binary + env ────────────────────────────
def _find_openclaw():
    """Find openclaw binary and build an env dict with node on PATH."""
    oc_bin = shutil.which('openclaw')
    if oc_bin:
        return oc_bin, None

    nvm_base = os.path.expanduser('~/.nvm/versions/node')
    if os.path.isdir(nvm_base):
        for entry in sorted(os.listdir(nvm_base), reverse=True):
            bin_dir = os.path.join(nvm_base, entry, 'bin')
            p = os.path.join(bin_dir, 'openclaw')
            if os.path.isfile(p) and os.access(p, os.X_OK):
                env = os.environ.copy()
                env['PATH'] = bin_dir + ':' + env.get('PATH', '/usr/bin:/bin')
                return p, env

    for d in ['/usr/local/bin', '/usr/local/lib/node_modules/.bin']:
        p = os.path.join(d, 'openclaw')
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p, None

    return 'openclaw', None

OC_BIN, OC_ENV = _find_openclaw()
