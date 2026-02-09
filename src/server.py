#!/usr/bin/env python3
"""
openclaw Monitor — real-time dashboard backend (SSE)

Usage:
    python3 src/server.py                  # default port 18765
    python3 src/server.py --port 9999
    python3 src/server.py --tailscale      # bind to Tailscale IP
"""

import http.server
import os
import signal
import socketserver
import sys

# Ensure src/ is on the import path so modules can find each other
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402  — handles --version exit, arg parsing
import tailscale  # noqa: E402
import cli_cache  # noqa: E402
from handler import Handler  # noqa: E402


# ── Tailscale binding ────────────────────────────────────────
BIND_HOST = '0.0.0.0'
if config.ARGS.tailscale:
    ts_ip = tailscale._get_tailscale_ip()
    if ts_ip:
        BIND_HOST = ts_ip
    else:
        print('\n  ERROR: --tailscale flag set but Tailscale is not available.')
        print('  Ensure Tailscale is installed and running (`tailscale status`).\n')
        sys.exit(1)


# ── Threaded server ──────────────────────────────────────────
class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads    = True
    allow_reuse_address = True


# ── Entry point ──────────────────────────────────────────────
if __name__ == '__main__':
    cli_cache.start()
    server = _Server((BIND_HOST, config.PORT), Handler)
    ver = config._get_version()
    url = f'http://{BIND_HOST}:{config.PORT}' if BIND_HOST != '0.0.0.0' else f'http://localhost:{config.PORT}'
    print(f'\n  openclaw Monitor  →  {url}')
    print(f'  version         : {ver["version"]}')

    from auth import _auth_status  # noqa: E402
    _status = _auth_status()
    _status_label = {'enabled': 'enabled (password required)',
                     'locked':  'LOCKED (auth file missing — all access denied)',
                     'disabled': 'disabled (no .auth file)'}
    print(f'  auth            : {_status_label.get(_status, _status)}')
    if config.ARGS.tailscale:
        print(f'  tailscale       : {BIND_HOST}')
    print(f'  session dir     : {config.SESSION_DIR}')
    print(f'  today log       : {config.TODAY_LOG}\n')
    signal.signal(signal.SIGINT, lambda *_: (server.shutdown(), sys.exit(0)))
    server.serve_forever()
