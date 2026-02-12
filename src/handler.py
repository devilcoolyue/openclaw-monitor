"""
HTTP request handler: routing, auth guards, all API endpoints.
"""

import http.cookies
import http.server
import json
import os
import select
import socket
import subprocess
import tempfile
import time
from urllib.parse import urlparse

import config
import auth
import cli_cache
import diagnostics
import logs
import sessions
import jsonl
from sse import _begin_sse, _send_sse, _send_sse_heartbeat, _json_resp, _read_json_file


def _json_resp_status(handler, obj, status=200):
    body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _split_model_ref(ref: str):
    if not isinstance(ref, str) or '/' not in ref:
        return '', ref or ''
    provider, model_id = ref.split('/', 1)
    return provider, model_id


def _collect_model_options(cfg: dict):
    opts = []
    seen = set()

    providers = cfg.get('models', {}).get('providers', {})
    if isinstance(providers, dict):
        for provider, pdata in providers.items():
            models = pdata.get('models', []) if isinstance(pdata, dict) else []
            if not isinstance(models, list):
                continue
            for m in models:
                if not isinstance(m, dict):
                    continue
                model_id = m.get('id')
                if not isinstance(model_id, str) or not model_id:
                    continue
                val = f'{provider}/{model_id}'
                key = val.lower()
                if key in seen:
                    continue
                seen.add(key)
                opts.append({
                    'value': val,
                    'provider': str(provider),
                    'modelId': model_id,
                    'name': m.get('name') or ''
                })

    defaults_models = cfg.get('agents', {}).get('defaults', {}).get('models', {})
    if isinstance(defaults_models, dict):
        for val in defaults_models.keys():
            if not isinstance(val, str) or '/' not in val:
                continue
            key = val.lower()
            if key in seen:
                continue
            provider, model_id = _split_model_ref(val)
            seen.add(key)
            opts.append({
                'value': val,
                'provider': provider,
                'modelId': model_id,
                'name': ''
            })

    current = cfg.get('agents', {}).get('defaults', {}).get('model', {}).get('primary')
    if isinstance(current, str) and '/' in current and current.lower() not in seen:
        provider, model_id = _split_model_ref(current)
        opts.append({
            'value': current,
            'provider': provider,
            'modelId': model_id,
            'name': ''
        })

    opts.sort(key=lambda x: x['value'].lower())
    return opts


def _write_json_atomic(path: str, data):
    file_mode = 0o600
    try:
        file_mode = os.stat(path).st_mode & 0o777
    except OSError:
        pass

    parent = os.path.dirname(path) or '.'
    fd, tmp_path = tempfile.mkstemp(prefix='.openclaw-monitor.', suffix='.json', dir=parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write('\n')
        os.chmod(tmp_path, file_mode)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class Handler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=config.SERVE_DIR, **kwargs)

    # suppress per-request logging
    def log_message(self, *_): pass

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # client disconnected, nothing to do

    # ── auth guard ───────────────────────────────────────────
    def _require_auth(self, api=False):
        """Return True if request should be blocked (not authenticated)."""
        status = auth._auth_status()

        if status == 'disabled':
            return False
        if status == 'enabled' and auth._check_auth(self):
            return False

        # 'locked' → auth file missing/tampered, refuse everything
        if status == 'locked':
            if api:
                body = json.dumps({'error': 'System locked — auth file missing'}).encode()
                self.send_response(403)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = auth.LOCKED_HTML.encode('utf-8')
                self.send_response(403)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            return True

        # 'enabled' but not authenticated → login page
        if api:
            body = json.dumps({'error': 'Unauthorized'}).encode()
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = auth.LOGIN_HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        return True

    # ── routing ─────────────────────────────────────────────
    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/api/logout':
            return self._api_logout()
        if path == '/api/version':
            return _json_resp(self, config._get_version())

        is_api = path.startswith('/api/')
        if self._require_auth(api=is_api):
            return

        if   path == '/api/sessions':            return self._api_sessions()
        elif path == '/api/health':              return self._api_health()
        elif path == '/api/models':              return self._api_models()
        elif path == '/api/system':              return self._api_system()
        elif path == '/api/logs/stream':         return self._api_log_stream()
        elif path.startswith('/api/session/') and path.endswith('/stream'):
            sid = path[len('/api/session/'):-len('/stream')]
            return self._api_session_stream(sid)

        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path

        if path == '/api/login':
            return self._api_login()

        if self._require_auth(api=True):
            return

        if path == '/api/models/switch':
            return self._api_models_switch()

        self.send_error(404, 'Not Found')

    # ── POST /api/login ──────────────────────────────────────
    def _api_login(self):
        # If system is locked, reject all login attempts
        if auth._auth_status() == 'locked':
            resp = json.dumps({'ok': False, 'error': 'System locked — auth file missing'}).encode()
            self.send_response(403)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
            return

        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except (json.JSONDecodeError, ValueError):
            body = {}
        password = body.get('password', '')

        if auth._verify_password(password):
            token = auth._create_session()
            resp = json.dumps({'ok': True}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(resp)))
            self.send_header('Set-Cookie',
                f'{config.COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={config.SESSION_TTL}')
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
        cookie_header = self.headers.get('Cookie', '')
        if cookie_header:
            cookies = http.cookies.SimpleCookie()
            try:
                cookies.load(cookie_header)
                morsel = cookies.get(config.COOKIE_NAME)
                if morsel and morsel.value in auth.AUTH_SESSIONS:
                    del auth.AUTH_SESSIONS[morsel.value]
            except http.cookies.CookieError:
                pass

        resp = json.dumps({'ok': True}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(resp)))
        self.send_header('Set-Cookie',
            f'{config.COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0')
        self.end_headers()
        self.wfile.write(resp)

    # ── GET /api/sessions ───────────────────────────────────
    def _api_sessions(self):
        sess = []
        try:
            r = subprocess.run([config.OC_BIN, 'sessions'],
                               capture_output=True, text=True, timeout=5, env=config.OC_ENV)
            if r.returncode == 0 and r.stdout.strip():
                sess = sessions._parse_oc_sessions(r.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

        if not sess:
            sess = sessions._scan_session_files()

        _json_resp(self, sess)

    # ── GET /api/health ─────────────────────────────────────
    def _api_health(self):
        # Socket probe to gateway port — ~0.1 ms, no subprocess
        gw_online = False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            gw_online = s.connect_ex((config.GATEWAY_HOST, config.GATEWAY_PORT)) == 0
            s.close()
        except OSError:
            pass

        result = {
            'openclaw_available': gw_online,
            'session_dir_exists': os.path.isdir(config.SESSION_DIR),
            'today_log_exists':   os.path.isfile(config.TODAY_LOG),
        }
        _json_resp(self, result)

    # ── GET /api/models ─────────────────────────────────────
    def _api_models(self):
        cfg = _read_json_file(config.OPENCLAW_CONFIG)
        if not isinstance(cfg, dict):
            return _json_resp_status(self, {
                'ok': False,
                'error': f'Failed to parse config file: {config.OPENCLAW_CONFIG}'
            }, 500)

        current = cfg.get('agents', {}).get('defaults', {}).get('model', {}).get('primary')
        _json_resp(self, {
            'ok': True,
            'configPath': config.OPENCLAW_CONFIG,
            'current': current if isinstance(current, str) else '',
            'options': _collect_model_options(cfg),
        })

    # ── POST /api/models/switch ─────────────────────────────
    def _api_models_switch(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except (json.JSONDecodeError, ValueError):
            body = {}

        target = body.get('target', '')
        if not isinstance(target, str) or not target.strip():
            return _json_resp_status(self, {'ok': False, 'error': 'Missing target model'}, 400)

        requested = target.strip()
        with config.MODEL_SWITCH_LOCK:
            cfg = _read_json_file(config.OPENCLAW_CONFIG)
            if not isinstance(cfg, dict):
                return _json_resp_status(self, {
                    'ok': False,
                    'error': f'Failed to parse config file: {config.OPENCLAW_CONFIG}'
                }, 500)

            options = _collect_model_options(cfg)
            option_map = {}
            for opt in options:
                val = opt.get('value')
                if isinstance(val, str) and val:
                    option_map[val.lower()] = val

            canonical = option_map.get(requested.lower())
            if not canonical:
                return _json_resp_status(self, {
                    'ok': False,
                    'error': f'Target model not found: {requested}'
                }, 400)

            agents_cfg = cfg.setdefault('agents', {})
            if not isinstance(agents_cfg, dict):
                agents_cfg = {}
                cfg['agents'] = agents_cfg
            defaults = agents_cfg.setdefault('defaults', {})
            if not isinstance(defaults, dict):
                defaults = {}
                agents_cfg['defaults'] = defaults

            model_cfg = defaults.setdefault('model', {})
            if not isinstance(model_cfg, dict):
                model_cfg = {}
                defaults['model'] = model_cfg

            current = model_cfg.get('primary')
            changed_primary = not isinstance(current, str) or current.lower() != canonical.lower()
            model_cfg['primary'] = canonical

            defaults_models = defaults.get('models')
            if not isinstance(defaults_models, dict):
                defaults_models = {}
                defaults['models'] = defaults_models

            has_case_insensitive = any(
                isinstance(k, str) and k.lower() == canonical.lower()
                for k in defaults_models.keys()
            )
            added_model_key = False
            if not has_case_insensitive:
                defaults_models[canonical] = {}
                added_model_key = True

            changed = changed_primary or added_model_key
            if changed:
                try:
                    _write_json_atomic(config.OPENCLAW_CONFIG, cfg)
                except OSError as e:
                    return _json_resp_status(self, {
                        'ok': False,
                        'error': f'Failed to write config: {e}'
                    }, 500)

                try:
                    p = subprocess.run(
                        [config.OC_BIN, 'gateway', 'restart'],
                        capture_output=True,
                        text=True,
                        timeout=20,
                        env=config.OC_ENV
                    )
                except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
                    return _json_resp_status(self, {
                        'ok': False,
                        'changed': True,
                        'current': canonical,
                        'error': f'Gateway restart failed: {e}'
                    }, 500)

                if p.returncode != 0:
                    err = (p.stderr or p.stdout or '').strip() or 'Gateway restart failed'
                    return _json_resp_status(self, {
                        'ok': False,
                        'changed': True,
                        'current': canonical,
                        'error': err
                    }, 500)

            _json_resp(self, {
                'ok': True,
                'changed': changed,
                'current': canonical,
                'gatewayRestarted': changed,
            })

    # ── GET /api/system ────────────────────────────────────
    def _api_system(self):
        result = {}

        # CLI data from background cache
        cache = cli_cache.get_cache()
        result['channel_health'] = cache['channel_health'] or {'error': 'loading'}
        result['presence'] = cache['presence'] or {'error': 'loading'}
        last = cache['lastUpdated']
        result['cli_lastUpdated'] = last
        result['cli_age'] = round(time.time() - last, 1) if last else None

        # File-based diagnostics
        result['diagnostics'] = diagnostics._file_diagnostics()

        # File-based data
        sessions_data = _read_json_file(config.SESSIONS_JSON)

        # Context Window
        ctx = []
        if isinstance(sessions_data, dict):
            for key, s in sessions_data.items():
                if not isinstance(s, dict):
                    continue
                sid = s.get('sessionId', key)
                ct = s.get('contextTokens')
                tt = s.get('totalTokens')
                if ct is not None or tt is not None:
                    pct = round(tt / ct * 100, 1) if ct and tt and ct > 0 else None
                    ctx.append({'sessionId': sid, 'contextTokens': ct, 'totalTokens': tt, 'percent': pct})
        result['context_window'] = ctx

        # System Prompt Report
        spr = []
        if isinstance(sessions_data, dict):
            for key, s in sessions_data.items():
                if not isinstance(s, dict):
                    continue
                report = s.get('systemPromptReport')
                if report:
                    spr.append({'sessionId': s.get('sessionId', key), 'report': report})
        result['system_prompt_report'] = spr

        # Skills Snapshot
        skills = []
        if isinstance(sessions_data, dict):
            for key, s in sessions_data.items():
                if not isinstance(s, dict):
                    continue
                snap = s.get('skillsSnapshot')
                if snap:
                    skills.append({'sessionId': s.get('sessionId', key), 'snapshot': snap})
        result['skills_snapshot'] = skills

        # Compaction History
        compaction = []
        if isinstance(sessions_data, dict):
            for key, s in sessions_data.items():
                if not isinstance(s, dict):
                    continue
                cc = s.get('compactionCount')
                if cc is not None:
                    compaction.append({'sessionId': s.get('sessionId', key), 'compactionCount': cc})
        result['compaction_history'] = compaction

        # Devices
        paired = _read_json_file(config.DEVICES_PAIRED)
        pending = _read_json_file(config.DEVICES_PENDING)
        result['devices'] = {'paired': paired, 'pending': pending}

        # Cron Jobs
        result['cron_jobs'] = _read_json_file(config.CRON_JOBS)

        # Update Check
        result['update_check'] = _read_json_file(config.UPDATE_CHECK)

        # Exec Approvals
        result['exec_approvals'] = _read_json_file(config.EXEC_APPROVALS)

        _json_resp(self, result)

    # ── SSE /api/logs/stream ────────────────────────────────
    def _api_log_stream(self):
        with config._log_stream_lock:
            if config._log_stream_count >= config.MAX_LOG_STREAMS:
                _begin_sse(self)
                _send_sse(self, 'status', {
                    'type': 'warn',
                    'message': f'Too many log streams ({config.MAX_LOG_STREAMS} max). '
                               'Close another tab and retry.'
                })
                return
            config._log_stream_count += 1

        _begin_sse(self)
        try:
            if not logs._tail_log_file(self):
                _send_sse(self, 'status', {
                    'type': 'warn',
                    'message': 'No log file available. Ensure openclaw is running.'
                })
        finally:
            with config._log_stream_lock:
                config._log_stream_count -= 1

    # ── SSE /api/session/<id>/stream ────────────────────────
    def _api_session_stream(self, session_id):
        with config._session_stream_lock:
            if config._session_stream_count >= config.MAX_SESSION_STREAMS:
                _begin_sse(self)
                _send_sse(self, 'status', {
                    'type': 'warn',
                    'message': f'Too many session streams ({config.MAX_SESSION_STREAMS} max). '
                               'Close another tab and retry.'
                })
                return
            config._session_stream_count += 1

        _begin_sse(self)

        session_file = os.path.join(config.SESSION_DIR, f'{session_id}.jsonl')
        if not os.path.isfile(session_file):
            _send_sse(self, 'status', {
                'type': 'error',
                'message': f'Session file not found: {session_file}'
            })
            with config._session_stream_lock:
                config._session_stream_count -= 1
            return

        proc = None
        try:
            # replay history
            with open(session_file) as fh:
                for line in fh:
                    parsed = jsonl._parse_jsonl_line(line)
                    if parsed and not _send_sse(self, 'session_event', parsed):
                        return

            _send_sse(self, 'history_done', {})

            # tail for new lines (non-blocking with select)
            proc = subprocess.Popen(
                ['tail', '-f', '-n', '0', session_file],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            fd = proc.stdout.fileno()
            client_fd = self.connection.fileno()
            buf = b''

            while True:
                readable, _, _ = select.select([fd, client_fd], [], [], 15)

                if not readable:
                    if not _send_sse_heartbeat(self):
                        break
                    continue

                if client_fd in readable:
                    break

                if fd in readable:
                    chunk = os.read(fd, 8192)
                    if not chunk:
                        break
                    buf += chunk
                    while b'\n' in buf:
                        raw, buf = buf.split(b'\n', 1)
                        parsed = jsonl._parse_jsonl_line(
                            raw.decode('utf-8', errors='replace'))
                        if parsed and not _send_sse(self, 'session_event', parsed):
                            return
        finally:
            if proc:
                proc.kill()
                proc.wait()
            with config._session_stream_lock:
                config._session_stream_count -= 1
