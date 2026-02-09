"""
Log file resolution, tailing, parsing, and classification.
"""

import glob as globmod
import json
import os
import subprocess
import time
from datetime import datetime

import config
from sse import _send_sse


def _resolve_today_log():
    """Find today's log file, fall back to most recent one."""
    today = os.path.join(config.LOG_DIR,
                         f"openclaw-{datetime.now().strftime('%Y-%m-%d')}.log")
    if os.path.isfile(today):
        return today
    candidates = sorted(globmod.glob(os.path.join(config.LOG_DIR, 'openclaw-*.log')),
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

            now = time.monotonic()
            if now - window_start >= 1.0:
                sent_this_sec = 0
                window_start  = now
            if sent_this_sec >= config.MAX_LOG_LINES_SEC:
                continue
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
    m = config.TS_RE.match(line)
    if m:
        ts = m.group(1)
        if len(ts) <= 12:
            ts = datetime.now().strftime('%Y-%m-%d') + 'T' + ts
        return ts
    return None


def _extract_timestamp_from_data(data: dict, raw_line: str = '') -> str | None:
    """Extract timestamp from parsed JSON data or raw line."""
    ts = data.get('timestamp') or data.get('time') or data.get('ts') or data.get('@timestamp')
    if ts:
        return ts

    meta = data.get('_meta')
    if meta:
        ts = meta.get('date') if isinstance(meta, dict) else None
        if ts:
            return ts

    return _extract_timestamp(raw_line) if raw_line else None


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
