"""
Background CLI cache: runs openclaw CLI commands periodically and caches results.
Run commands sequentially to avoid memory spikes — each openclaw CLI
process is a Node.js app that consumes ~500MB RAM.
"""

import json
import re
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
_ANSI_RE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')


def _strip_ansi(text):
    """Remove ANSI color/control sequences from text output."""
    if not text:
        return ''
    return _ANSI_RE.sub('', text)


def _extract_json_payload(text):
    """Extract the most likely JSON payload from noisy CLI output."""
    if not text:
        return None

    decoder = json.JSONDecoder()
    best_obj = None
    # Prefer candidates that consume the full tail, then longer payloads.
    best_score = (-1, -1)

    for idx, ch in enumerate(text):
        if ch not in '{[':
            continue
        try:
            obj, end = decoder.raw_decode(text[idx:])
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, (dict, list)):
            continue

        trailing = text[idx + end:].strip()
        score = (1 if trailing == '' else 0, end)
        if score > best_score:
            best_score = score
            best_obj = obj

    return best_obj


def _run_cli_cached(cmd, timeout=30):
    """Run a CLI command, return parsed result."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=config.OC_ENV)
        out = (r.stdout or '').strip()
        err = (r.stderr or '').strip()
        clean_out = _strip_ansi(out)
        clean_err = _strip_ansi(err)

        if r.returncode != 0:
            return {'raw': clean_out or out, 'stderr': clean_err or err, 'exitCode': r.returncode}

        for candidate in (out, clean_out):
            try:
                return json.loads(candidate)
            except (json.JSONDecodeError, ValueError):
                pass

            extracted = _extract_json_payload(candidate)
            if extracted is not None:
                return extracted

        return {'raw': clean_out or out}
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
