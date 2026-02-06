#!/usr/bin/env python3
"""
openclaw Monitor — real-time dashboard backend (SSE)

Usage:
    python3 server.py          # default port 8888
    python3 server.py --port 9999
"""

import http.server
import socketserver
import subprocess
import json
import os
import re
import sys
import signal
from urllib.parse import urlparse
from datetime import datetime

# ── Config ────────────────────────────────────────────────────
PORT        = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == '--port' else 8888
SERVE_DIR   = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR = os.path.expanduser("~/.openclaw/agents/main/sessions")
LOG_DIR     = "/tmp/openclaw"
TODAY_LOG   = os.path.join(LOG_DIR, f"openclaw-{datetime.now().strftime('%Y-%m-%d')}.log")

UUID_RE     = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)
# Pattern for extracting timestamp from log lines (e.g., "2024-01-15 14:30:45" or "14:30:45.123")
TS_RE       = re.compile(r'^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?|\d{2}:\d{2}:\d{2}(?:\.\d+)?)')


# ── Request Handler ──────────────────────────────────────────
class Handler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    # suppress per-request logging
    def log_message(self, *_): pass

    # ── routing ─────────────────────────────────────────────
    def do_GET(self):
        path = urlparse(self.path).path

        if   path == '/api/sessions':            return self._api_sessions()
        elif path == '/api/health':              return self._api_health()
        elif path == '/api/logs/stream':         return self._api_log_stream()
        elif path.startswith('/api/session/') and path.endswith('/stream'):
            sid = path[len('/api/session/'):-len('/stream')]
            return self._api_session_stream(sid)

        # everything else → static files (index.html)
        return super().do_GET()

    def do_DELETE(self):
        path = urlparse(self.path).path

        if path.startswith('/api/session/'):
            sid = path[len('/api/session/'):]
            return self._api_delete_session(sid)

        self.send_error(404, 'Not Found')

    # ── DELETE /api/session/<id> ─────────────────────────────
    def _api_delete_session(self, session_id):
        # validate session_id format (UUID)
        if not UUID_RE.fullmatch(session_id):
            self.send_error(400, 'Invalid session ID format')
            return

        session_file = os.path.join(SESSION_DIR, f'{session_id}.jsonl')
        if not os.path.isfile(session_file):
            self.send_error(404, 'Session not found')
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
        _begin_sse(self)
        proc = None
        try:
            proc = subprocess.Popen(
                ['openclaw', 'logs', '--follow', '--json'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            for raw in iter(proc.stdout.readline, ''):
                line = raw.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    data = {'raw': line}

                if 'type' not in data:
                    data['type'] = _classify(data.get('raw', ''))
                if not data.get('raw'):
                    data['raw'] = line

                # Ensure timestamp exists - extract from JSON fields or raw line
                if 'timestamp' not in data:
                    ts = _extract_timestamp_from_data(data, line)
                    if ts:
                        data['timestamp'] = ts

                if not _send_sse(self, 'log', data):
                    break                          # client disconnected

        except (FileNotFoundError, OSError):
            # CLI unavailable → tail plain log file
            if not _tail_plain_log(self):
                _send_sse(self, 'status', {
                    'type': 'warn',
                    'message': 'openclaw CLI not found and no log file available. '
                               'Ensure openclaw is running.'
                })
        finally:
            if proc:
                proc.terminate()
                proc.wait()

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


# ── Tail plain log file (fallback) ───────────────────────────
def _tail_plain_log(handler):
    if not os.path.isfile(TODAY_LOG):
        return False
    proc = subprocess.Popen(
        ['tail', '-f', '-n', '200', TODAY_LOG],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        for raw in iter(proc.stdout.readline, ''):
            line = raw.strip()
            if not line:
                continue

            data = None
            # Only attempt JSON parse if line looks like JSON (starts with {)
            if line[0] == '{':
                try:
                    data = json.loads(line)
                    data.setdefault('raw', line)
                except json.JSONDecodeError:
                    pass

            if data is None:
                # Plain text line - use regex for timestamp
                ts = _extract_timestamp(line)
                data = {'raw': line, 'type': _classify(line)}
                if ts:
                    data['timestamp'] = ts
            else:
                # JSON parsed - extract timestamp from fields
                if 'type' not in data:
                    data['type'] = _classify(line)
                ts = _extract_timestamp_from_data(data, '')  # no regex fallback needed
                if ts:
                    data['timestamp'] = ts

            if not _send_sse(handler, 'log', data):
                break
    finally:
        proc.terminate()
        proc.wait()
    return True


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
    server = _Server(('0.0.0.0', PORT), Handler)
    print(f'\n  openclaw Monitor  →  http://localhost:{PORT}\n')
    print(f'  session dir : {SESSION_DIR}')
    print(f'  today log   : {TODAY_LOG}\n')
    signal.signal(signal.SIGINT, lambda *_: (server.shutdown(), sys.exit(0)))
    server.serve_forever()
