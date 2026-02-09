"""
Background CLI cache: runs openclaw CLI commands periodically and caches results.
Run commands sequentially to avoid memory spikes — each openclaw CLI
process is a Node.js app that consumes ~500MB RAM.
"""

import json
import subprocess
import threading
import time

import config

_cli_cache = {
    'channel_health': None,
    'presence': None,
    'lastUpdated': None,
}
_cli_cache_lock = threading.Lock()
_CLI_CACHE_INTERVAL = 120  # seconds between refreshes


def _run_cli_cached(cmd, timeout=30):
    """Run a CLI command, return parsed result."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=config.OC_ENV)
        out = r.stdout.strip()
        if r.returncode != 0:
            return {'raw': out, 'stderr': r.stderr.strip(), 'exitCode': r.returncode}
        try:
            return json.loads(out)
        except (json.JSONDecodeError, ValueError):
            pass
        for start_char, end_char in (('{', '}'), ('[', ']')):
            idx = out.find(start_char)
            if idx >= 0:
                ridx = out.rfind(end_char)
                if ridx > idx:
                    try:
                        return json.loads(out[idx:ridx + 1])
                    except (json.JSONDecodeError, ValueError):
                        pass
        return {'raw': out}
    except subprocess.TimeoutExpired:
        return {'error': 'timeout'}
    except FileNotFoundError:
        return {'error': 'openclaw not found'}
    except OSError as e:
        return {'error': str(e)}


def _cli_cache_worker():
    """Background thread: refresh CLI data periodically (sequentially)."""
    while True:
        try:
            ch = _run_cli_cached([config.OC_BIN, 'status', '--json'])
            with _cli_cache_lock:
                _cli_cache['channel_health'] = ch
                _cli_cache['lastUpdated'] = time.time()
        except Exception:
            pass
        try:
            pr = _run_cli_cached([config.OC_BIN, 'system', 'presence'])
            with _cli_cache_lock:
                _cli_cache['presence'] = pr
                _cli_cache['lastUpdated'] = time.time()
        except Exception:
            pass
        time.sleep(_CLI_CACHE_INTERVAL)


def get_cache():
    """Return a snapshot of the CLI cache."""
    with _cli_cache_lock:
        return {
            'channel_health': _cli_cache['channel_health'],
            'presence': _cli_cache['presence'],
            'lastUpdated': _cli_cache['lastUpdated'],
        }


def start():
    """Start the background cache worker thread."""
    t = threading.Thread(target=_cli_cache_worker, daemon=True)
    t.start()
