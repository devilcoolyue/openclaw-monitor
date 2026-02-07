#!/usr/bin/env python3
"""
openclaw Monitor — real-time dashboard backend (SSE)

Usage:
    python3 src/server.py                  # default port 18765
    python3 src/server.py --port 9999
    python3 src/server.py --tailscale      # bind to Tailscale IP
"""

import argparse
import glob as globmod
import hashlib
import http.server
import http.cookies
import secrets
import socketserver
import subprocess
import json
import os
import re
import sys
import signal
import threading
import time
from urllib.parse import urlparse
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

SESSION_DIR = os.path.expanduser("~/.openclaw/agents/main/sessions")
LOG_DIR     = "/tmp/openclaw"
TODAY_LOG   = os.path.join(LOG_DIR, f"openclaw-{datetime.now().strftime('%Y-%m-%d')}.log")

UUID_RE     = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)
# Pattern for extracting timestamp from log lines (e.g., "2024-01-15 14:30:45" or "14:30:45.123")
TS_RE       = re.compile(r'^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?|\d{2}:\d{2}:\d{2}(?:\.\d+)?)')

# ── SSE concurrency & rate limiting ─────────────────────────
MAX_LOG_STREAMS     = 2           # max concurrent /api/logs/stream connections
MAX_LOG_LINES_SEC   = 50          # throttle: max lines pushed per second
_log_stream_count   = 0
_log_stream_lock    = threading.Lock()

# ── Auth System ──────────────────────────────────────────────
AUTH_FILE      = os.path.join(BASE_DIR, '.auth')
SESSION_TTL    = 7 * 24 * 3600  # 7 days
COOKIE_NAME    = 'monitor_sid'
AUTH_SESSIONS  = {}  # token → expiry_timestamp

def _load_auth():
    """Load .auth file, return (salt, hash) or None if auth disabled."""
    try:
        with open(AUTH_FILE) as f:
            line = f.read().strip()
        if ':' in line:
            salt, h = line.split(':', 1)
            return (salt, h)
    except (OSError, ValueError):
        pass
    return None

def _verify_password(password):
    """Check password against stored salt:hash."""
    creds = _load_auth()
    if not creds:
        return False
    salt, stored_hash = creds
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return secrets.compare_digest(h, stored_hash)

def _create_session():
    """Generate a new session token with TTL."""
    token = secrets.token_hex(32)
    AUTH_SESSIONS[token] = time.time() + SESSION_TTL
    return token

def _check_auth(handler):
    """Check if request has a valid session cookie. Returns True if authenticated."""
    cookie_header = handler.headers.get('Cookie', '')
    if not cookie_header:
        return False
    cookies = http.cookies.SimpleCookie()
    try:
        cookies.load(cookie_header)
    except http.cookies.CookieError:
        return False
    morsel = cookies.get(COOKIE_NAME)
    if not morsel:
        return False
    token = morsel.value
    expiry = AUTH_SESSIONS.get(token)
    if not expiry:
        return False
    if time.time() > expiry:
        del AUTH_SESSIONS[token]
        return False
    return True

AUTH_ENABLED = _load_auth() is not None

LOGIN_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>openclaw monitor — Login</title>
<style>
:root{--bg-0:#0a0e13;--bg-1:#111519;--bg-2:#161b22;--bg-3:#1c2330;--border:#1e2530;--t0:#e6edf3;--t1:#c9d1d9;--t2:#8b949e;--t3:#6e7681;--accent:#58a6ff;--green:#3fb950;--red:#ff7b72}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{font-family:'SF Mono','Fira Code','Consolas','Courier New',monospace;background:var(--bg-0);color:var(--t1);display:flex;align-items:center;justify-content:center}
.login-box{width:340px;background:var(--bg-1);border:1px solid var(--border);border-radius:10px;padding:36px 30px 30px}
.login-logo{font-size:16px;font-weight:700;color:var(--t0);text-align:center;margin-bottom:6px;letter-spacing:-.3px}
.login-logo em{font-style:normal;color:var(--accent)}
.login-sub{font-size:11px;color:var(--t3);text-align:center;margin-bottom:24px}
.login-label{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--t3);font-weight:600;margin-bottom:6px;display:block}
.login-input{width:100%;padding:9px 12px;border-radius:6px;border:1px solid var(--border);background:var(--bg-2);color:var(--t0);font-family:inherit;font-size:13px;outline:none;transition:border-color .15s}
.login-input:focus{border-color:var(--accent)}
.login-btn{width:100%;margin-top:18px;padding:10px;border-radius:6px;border:none;background:var(--accent);color:#fff;font-family:inherit;font-size:13px;font-weight:600;cursor:pointer;transition:opacity .15s}
.login-btn:hover{opacity:.9}
.login-btn:disabled{opacity:.5;cursor:not-allowed}
.login-err{color:var(--red);font-size:11px;text-align:center;margin-top:12px;min-height:16px}
</style>
</head>
<body>
<div class="login-box">
  <div class="login-logo"><em>openclaw</em> monitor</div>
  <div class="login-sub">Authentication required</div>
  <form id="login-form">
    <label class="login-label" for="pw">Password</label>
    <input class="login-input" id="pw" type="password" autocomplete="current-password" autofocus>
    <button class="login-btn" type="submit">Sign In</button>
  </form>
  <div class="login-err" id="err"></div>
</div>
<script>
document.getElementById('login-form').addEventListener('submit', async function(e) {
  e.preventDefault();
  const btn = this.querySelector('button');
  const err = document.getElementById('err');
  btn.disabled = true;
  err.textContent = '';
  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({password: document.getElementById('pw').value})
    });
    const data = await res.json();
    if (data.ok) {
      location.reload();
    } else {
      err.textContent = data.error || 'Invalid password';
      btn.disabled = false;
    }
  } catch(ex) {
    err.textContent = 'Connection error';
    btn.disabled = false;
  }
});
</script>
</body>
</html>'''

# ── Tailscale binding ────────────────────────────────────────
def _get_tailscale_ip():
    """Detect Tailscale IPv4 address."""
    try:
        r = subprocess.run(['tailscale', 'ip', '-4'],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None

BIND_HOST = '0.0.0.0'
if ARGS.tailscale:
    ts_ip = _get_tailscale_ip()
    if ts_ip:
        BIND_HOST = ts_ip
    else:
        print('\n  ERROR: --tailscale flag set but Tailscale is not available.')
        print('  Ensure Tailscale is installed and running (`tailscale status`).\n')
        sys.exit(1)


# ── Request Handler ──────────────────────────────────────────
class Handler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    # suppress per-request logging
    def log_message(self, *_): pass

    # ── auth guard ───────────────────────────────────────────
    def _require_auth(self, api=False):
        """Return True if request should be blocked (not authenticated).
        For page requests, serves login HTML. For API requests, sends 401."""
        if not AUTH_ENABLED:
            return False
        if _check_auth(self):
            return False
        if api:
            body = json.dumps({'error': 'Unauthorized'}).encode()
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = LOGIN_HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        return True

    # ── routing ─────────────────────────────────────────────
    def do_GET(self):
        path = urlparse(self.path).path

        # Logout and version are always accessible (no auth required)
        if path == '/api/logout':
            return self._api_logout()
        if path == '/api/version':
            return _json_resp(self, _get_version())

        # Auth check for all other routes
        is_api = path.startswith('/api/')
        if self._require_auth(api=is_api):
            return

        if   path == '/api/sessions':            return self._api_sessions()
        elif path == '/api/health':              return self._api_health()
        elif path == '/api/logs/stream':         return self._api_log_stream()
        elif path.startswith('/api/session/') and path.endswith('/stream'):
            sid = path[len('/api/session/'):-len('/stream')]
            return self._api_session_stream(sid)

        # everything else → static files (index.html)
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path

        # Login is always accessible (exempt from auth)
        if path == '/api/login':
            return self._api_login()

        # Auth check for any other POST
        if self._require_auth(api=True):
            return

        self.send_error(404, 'Not Found')

    def do_DELETE(self):
        path = urlparse(self.path).path

        # Auth check
        if self._require_auth(api=True):
            return

        if path.startswith('/api/session/'):
            sid = path[len('/api/session/'):]
            return self._api_delete_session(sid)

        self.send_error(404, 'Not Found')

    # ── POST /api/login ──────────────────────────────────────
    def _api_login(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except (json.JSONDecodeError, ValueError):
            body = {}
        password = body.get('password', '')

        if _verify_password(password):
            token = _create_session()
            resp = json.dumps({'ok': True}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(resp)))
            self.send_header('Set-Cookie',
                f'{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL}')
            self.end_headers()
            self.wfile.write(resp)
        else:
            resp = json.dumps({'ok': False, 'error': 'Invalid password'}).encode()
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

    # ── GET /api/logout ──────────────────────────────────────
    def _api_logout(self):
        # Invalidate server-side session
        cookie_header = self.headers.get('Cookie', '')
        if cookie_header:
            cookies = http.cookies.SimpleCookie()
            try:
                cookies.load(cookie_header)
                morsel = cookies.get(COOKIE_NAME)
                if morsel and morsel.value in AUTH_SESSIONS:
                    del AUTH_SESSIONS[morsel.value]
            except http.cookies.CookieError:
                pass

        resp = json.dumps({'ok': True}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(resp)))
        # Clear cookie
        self.send_header('Set-Cookie',
            f'{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0')
        self.end_headers()
        self.wfile.write(resp)

    # ── DELETE /api/session/<id> ─────────────────────────────
    def _api_delete_session(self, session_id):
        # validate session_id format (UUID)
        if not UUID_RE.fullmatch(session_id):
            self.send_error(400, 'Invalid session ID format')
            return

        session_file = _find_session_file(session_id)
        if not session_file:
            # file already gone — treat as success
            _json_resp(self, {'success': True, 'id': session_id})
            return

        try:
            os.remove(session_file)
            _json_resp(self, {'success': True, 'id': session_id})
        except OSError as e:
            self.send_error(500, f'Failed to delete: {e}')

    # ── GET /api/sessions ───────────────────────────────────
    def _api_sessions(self):
        sessions = []
        # try CLI first
        try:
            r = subprocess.run(['openclaw', 'sessions'],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                sessions = _parse_oc_sessions(r.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

        # fallback: scan JSONL directory
        if not sessions:
            sessions = _scan_session_files()

        _json_resp(self, sessions)

    # ── GET /api/health ─────────────────────────────────────
    def _api_health(self):
        result = {
            'openclaw_available': False,
            'session_dir_exists': os.path.isdir(SESSION_DIR),
            'today_log_exists':   os.path.isfile(TODAY_LOG),
        }
        try:
            r = subprocess.run(['openclaw', 'health'],
                               capture_output=True, text=True, timeout=5)
            result['openclaw_available'] = (r.returncode == 0)
            result['output'] = r.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        _json_resp(self, result)

    # ── SSE /api/logs/stream ────────────────────────────────
    def _api_log_stream(self):
        global _log_stream_count

        # ── concurrency guard ──
        with _log_stream_lock:
            if _log_stream_count >= MAX_LOG_STREAMS:
                _begin_sse(self)
                _send_sse(self, 'status', {
                    'type': 'warn',
                    'message': f'Too many log streams ({MAX_LOG_STREAMS} max). '
                               'Close another tab and retry.'
                })
                return
            _log_stream_count += 1

        _begin_sse(self)
        try:
            if not _tail_log_file(self):
                _send_sse(self, 'status', {
                    'type': 'warn',
                    'message': 'No log file available. Ensure openclaw is running.'
                })
        finally:
            with _log_stream_lock:
                _log_stream_count -= 1

    # ── SSE /api/session/<id>/stream ────────────────────────
    def _api_session_stream(self, session_id):
        _begin_sse(self)

        session_file = os.path.join(SESSION_DIR, f'{session_id}.jsonl')
        if not os.path.isfile(session_file):
            _send_sse(self, 'status', {
                'type': 'error',
                'message': f'Session file not found: {session_file}'
            })
            return

        proc = None
        try:
            # ① replay history
            with open(session_file) as fh:
                for line in fh:
                    parsed = _parse_jsonl_line(line)
                    if parsed and not _send_sse(self, 'session_event', parsed):
                        return

            _send_sse(self, 'history_done', {})

            # ② tail for new lines
            proc = subprocess.Popen(
                ['tail', '-f', '-n', '0', session_file],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            for raw in iter(proc.stdout.readline, ''):
                parsed = _parse_jsonl_line(raw)
                if parsed and not _send_sse(self, 'session_event', parsed):
                    break
        finally:
            if proc:
                proc.terminate()
                proc.wait()


# ── SSE helpers ───────────────────────────────────────────────
def _begin_sse(handler):
    handler.send_response(200)
    handler.send_header('Content-Type',  'text/event-stream')
    handler.send_header('Cache-Control', 'no-cache')
    handler.send_header('Connection',    'keep-alive')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.end_headers()

def _send_sse(handler, event, data):
    """Write one SSE event. Returns False on broken pipe."""
    payload = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    try:
        handler.wfile.write(payload.encode('utf-8'))
        handler.wfile.flush()
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False

def _json_resp(handler, obj):
    body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    handler.send_response(200)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


# ── Tail log file directly (no gateway RPC) ─────────────────
def _resolve_today_log():
    """Find today's log file, fall back to most recent one."""
    today = os.path.join(LOG_DIR,
                         f"openclaw-{datetime.now().strftime('%Y-%m-%d')}.log")
    if os.path.isfile(today):
        return today
    # fall back to newest log file in LOG_DIR
    candidates = sorted(globmod.glob(os.path.join(LOG_DIR, 'openclaw-*.log')),
                        key=os.path.getmtime, reverse=True)
    return candidates[0] if candidates else None


def _tail_log_file(handler):
    log_file = _resolve_today_log()
    if not log_file:
        return False

    proc = subprocess.Popen(
        ['tail', '-f', '-n', '200', log_file],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        sent_this_sec = 0
        window_start  = time.monotonic()

        for raw in iter(proc.stdout.readline, ''):
            line = raw.strip()
            if not line:
                continue

            # ── rate limiting ──
            now = time.monotonic()
            if now - window_start >= 1.0:
                sent_this_sec = 0
                window_start  = now
            if sent_this_sec >= MAX_LOG_LINES_SEC:
                continue                       # drop excess lines
            sent_this_sec += 1

            data = _parse_log_line(line)

            if not _send_sse(handler, 'log', data):
                break
    finally:
        proc.terminate()
        proc.wait()
    return True


def _parse_log_line(line: str) -> dict:
    """Parse a single log line (JSON or plain text) into an SSE payload."""
    data = None
    if line and line[0] == '{':
        try:
            data = json.loads(line)
            data.setdefault('raw', line)
        except json.JSONDecodeError:
            pass

    if data is None:
        ts = _extract_timestamp(line)
        data = {'raw': line, 'type': _classify(line)}
        if ts:
            data['timestamp'] = ts
    else:
        if 'type' not in data:
            data['type'] = _classify(line)
        ts = _extract_timestamp_from_data(data, '')
        if ts:
            data['timestamp'] = ts

    return data


def _extract_timestamp(line: str) -> str | None:
    """Extract timestamp from log line if present."""
    m = TS_RE.match(line)
    if m:
        ts = m.group(1)
        # If only time (no date), prepend today's date
        if len(ts) <= 12:  # HH:MM:SS or HH:MM:SS.mmm
            ts = datetime.now().strftime('%Y-%m-%d') + 'T' + ts
        return ts
    return None


def _extract_timestamp_from_data(data: dict, raw_line: str = '') -> str | None:
    """Extract timestamp from parsed JSON data or raw line."""
    # Fast path: direct get() chain (single dict lookup each, short-circuit on first truthy)
    ts = data.get('timestamp') or data.get('time') or data.get('ts') or data.get('@timestamp')
    if ts:
        return ts

    # Check nested _meta.date only if top-level not found
    meta = data.get('_meta')
    if meta:
        ts = meta.get('date') if isinstance(meta, dict) else None
        if ts:
            return ts

    # Fallback to regex only as last resort
    return _extract_timestamp(raw_line) if raw_line else None


# ── Parsers ───────────────────────────────────────────────────
def _classify(line: str) -> str:
    ll = line.lower()
    if 'enqueue' in ll:                          return 'enqueue'
    if 'dequeue' in ll:                          return 'dequeue'
    if 'run start' in ll or 'run_start' in ll:   return 'run_start'
    if 'run done'  in ll or 'run_done'  in ll:   return 'run_done'
    if 'tool start' in ll or 'tool_start' in ll: return 'tool_start'
    if 'tool end'   in ll or 'tool_end'   in ll: return 'tool_end'
    if 'session state' in ll:                    return 'session_state'
    if 'error' in ll:                            return 'error'
    if 'warn'  in ll:                            return 'warn'
    return 'other'


def _find_session_file(session_id: str):
    """Locate session JSONL file — check SESSION_DIR first, then search ~/.openclaw."""
    # standard path
    path = os.path.join(SESSION_DIR, f'{session_id}.jsonl')
    if os.path.isfile(path):
        return path
    # search under ~/.openclaw recursively
    oc_root = os.path.expanduser('~/.openclaw')
    fname = f'{session_id}.jsonl'
    if os.path.isdir(oc_root):
        for dirpath, _, filenames in os.walk(oc_root):
            if fname in filenames:
                return os.path.join(dirpath, fname)
    return None


def _parse_oc_sessions(output: str) -> list:
    """Parse `openclaw sessions` table output."""
    sessions = []
    for line in output.splitlines():
        line = line.strip()
        if not line or any(c in line for c in '┌┐└┘├┤─│═'):
            continue
        m = UUID_RE.search(line)
        if not m:
            continue
        sid  = m.group(0)
        path = os.path.join(SESSION_DIR, f'{sid}.jsonl')
        info = {'id': sid, 'file': path, 'raw_line': line}
        if os.path.isfile(path):
            mtime = os.path.getmtime(path)
            info['mtime'] = mtime
            info.update(_extract_session_info(path, mtime))
        sessions.append(info)
    return sessions


def _scan_session_files() -> list:
    if not os.path.isdir(SESSION_DIR):
        return []
    entries = []
    for name in os.listdir(SESSION_DIR):
        if not name.endswith('.jsonl'):
            continue
        path = os.path.join(SESSION_DIR, name)
        sid  = name[:-len('.jsonl')]
        mtime = os.path.getmtime(path)
        info = _extract_session_info(path, mtime)
        info['id']    = sid
        info['file']  = path
        info['mtime'] = mtime
        entries.append(info)
    entries.sort(key=lambda e: e.get('mtime', 0), reverse=True)
    return entries


def _extract_session_info(path: str, mtime: float = None) -> dict:
    info = {'provider': '', 'model': '', 'status': 'idle', 'message_count': 0}
    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cost = 0.0
    per_model_usage = {}  # model_name -> {input, output, cacheRead, cost}
    current_model = ''
    try:
        if mtime is None:
            mtime = os.path.getmtime(path)

        lines = open(path).readlines()
        info['message_count'] = len(lines)

        last_event_type = None
        last_role = None
        has_tool_result = {}  # track tool_call_id -> has_result

        for line in lines:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            for key in ('provider', 'model'):
                if key in obj:
                    info[key] = obj[key]
                msg = obj.get('message', {})
                if key in msg:
                    info[key] = msg[key]

            # Track current model for per-model usage
            if info['model']:
                current_model = info['model']

            # Accumulate token usage
            usage = obj.get('usage')
            if not usage:
                msg = obj.get('message', {})
                usage = msg.get('usage') if isinstance(msg, dict) else None
            if usage and isinstance(usage, dict):
                u_input = usage.get('input', 0) or 0
                u_output = usage.get('output', 0) or 0
                u_cache = usage.get('cacheRead', 0) or 0
                cost = usage.get('cost')
                u_cost = 0.0
                if isinstance(cost, dict):
                    u_cost = cost.get('total', 0) or 0
                elif isinstance(cost, (int, float)):
                    u_cost = cost

                total_input += u_input
                total_output += u_output
                total_cache_read += u_cache
                total_cost += u_cost

                # Per-model accumulation
                if current_model:
                    if current_model not in per_model_usage:
                        per_model_usage[current_model] = {'input': 0, 'output': 0, 'cacheRead': 0, 'cost': 0.0}
                    pm = per_model_usage[current_model]
                    pm['input'] += u_input
                    pm['output'] += u_output
                    pm['cacheRead'] += u_cache
                    pm['cost'] += u_cost

            # Track event types and roles
            last_event_type = obj.get('type', '')
            if last_event_type == 'message':
                msg = obj.get('message', {})
                last_role = msg.get('role', '')
                content = msg.get('content', [])

                # Track tool calls from assistant
                if last_role == 'assistant' and isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'toolCall':
                            tool_call_id = block.get('toolCallId', '')
                            if tool_call_id:
                                has_tool_result[tool_call_id] = False

                # Track tool results
                if last_role == 'toolResult':
                    tool_call_id = msg.get('toolCallId', '')
                    if tool_call_id:
                        has_tool_result[tool_call_id] = True

        # Check for pending tool calls (tool_call without tool_result)
        pending_tool_calls = [tid for tid, got_result in has_tool_result.items() if not got_result]

        # Determine status based on multiple heuristics
        is_processing = False
        if lines:
            is_recent = (datetime.now().timestamp() - mtime) < 30

            if pending_tool_calls:
                is_processing = True
            elif last_event_type in ('run_start', 'tool_start'):
                is_processing = True
            elif last_event_type == 'message' and last_role == 'user':
                is_processing = True
            elif last_event_type == 'message' and last_role == 'toolResult':
                is_processing = True
            elif is_recent and last_role == 'assistant':
                try:
                    last_obj = json.loads(lines[-1])
                    msg = last_obj.get('message', {})
                    content = msg.get('content', [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get('type') == 'toolCall':
                                is_processing = True
                                break
                except (json.JSONDecodeError, IndexError):
                    pass

        if is_processing:
            info['status'] = 'processing'
        else:
            info['status'] = 'idle'
            # Add idle_since timestamp (file last modified time)
            info['idle_since'] = mtime

        # Token usage summary
        total_tokens = total_input + total_output + total_cache_read
        if total_tokens > 0:
            info['usage'] = {
                'input': total_input,
                'output': total_output,
                'cacheRead': total_cache_read,
                'totalTokens': total_tokens,
                'cost': round(total_cost, 6)
            }

        # Per-model usage breakdown
        if per_model_usage:
            models = {}
            for m, u in per_model_usage.items():
                t = u['input'] + u['output'] + u['cacheRead']
                if t > 0:
                    models[m] = {
                        'input': u['input'],
                        'output': u['output'],
                        'cacheRead': u['cacheRead'],
                        'totalTokens': t,
                        'cost': round(u['cost'], 6)
                    }
            if models:
                info['models'] = models

    except OSError:
        pass
    return info


def _parse_jsonl_line(line: str):
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return {'role': 'raw', 'blocks': [{'type': 'text', 'content': line}]}

    if obj.get('type') != 'message':
        # non-message event (run_start, etc.)
        return {'role': 'meta', 'blocks': [], 'meta': obj}

    msg         = obj.get('message', {})
    role        = msg.get('role', 'unknown')
    raw_content = msg.get('content', [])
    if isinstance(raw_content, str):
        raw_content = [{'type': 'text', 'text': raw_content}]

    # toolResult is a special role — flatten to one text block
    if role == 'toolResult':
        text = ''
        for b in raw_content:
            if isinstance(b, dict) and b.get('type') == 'text':
                text = b.get('text', '')
                break
        return {'role': 'toolResult', 'blocks': [{'type': 'tool_result', 'content': text}]}

    blocks = []
    for b in raw_content:
        if not isinstance(b, dict):
            continue
        bt = b.get('type', '')
        if bt == 'thinking':
            blocks.append({'type': 'thinking', 'content': b.get('thinking', '')})
        elif bt == 'toolCall':
            blocks.append({
                'type':        'tool_call',
                'name':        b.get('name', ''),
                'arguments':   b.get('arguments', {}),
                'toolCallId':  b.get('toolCallId', '')
            })
        elif bt == 'text':
            blocks.append({'type': 'text', 'content': b.get('text', '')})

    return {'role': role, 'blocks': blocks}


# ── Threaded server ──────────────────────────────────────────
class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads    = True
    allow_reuse_address = True


# ── Entry point ──────────────────────────────────────────────
if __name__ == '__main__':
    server = _Server((BIND_HOST, PORT), Handler)
    ver = _get_version()
    url = f'http://{BIND_HOST}:{PORT}' if BIND_HOST != '0.0.0.0' else f'http://localhost:{PORT}'
    print(f'\n  openclaw Monitor  →  {url}')
    print(f'  version         : {ver["version"]}')
    if AUTH_ENABLED:
        print(f'  auth            : enabled (password required)')
    else:
        print(f'  auth            : disabled (no .auth file)')
    if ARGS.tailscale:
        print(f'  tailscale       : {BIND_HOST}')
    print(f'  session dir     : {SESSION_DIR}')
    print(f'  today log       : {TODAY_LOG}\n')
    signal.signal(signal.SIGINT, lambda *_: (server.shutdown(), sys.exit(0)))
    server.serve_forever()
