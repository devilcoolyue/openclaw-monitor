"""
File-based diagnostics (replaces `openclaw doctor`).
"""

import os

import config
from sse import _read_json_file


def _file_diagnostics():
    """Read-only diagnostics from files."""
    issues = []
    oc_root = os.path.expanduser('~/.openclaw')
    # Check state directory permissions
    try:
        mode = oct(os.stat(oc_root).st_mode)[-3:]
        if mode != '700':
            issues.append(f'State directory permissions are {mode}, recommend 700')
    except OSError:
        issues.append('State directory not found')
    # Check config file permissions
    cfg = os.path.join(oc_root, 'openclaw.json')
    try:
        mode = oct(os.stat(cfg).st_mode)[-3:]
        if mode not in ('600', '400'):
            issues.append(f'Config file permissions are {mode}, recommend 600')
    except OSError:
        issues.append('Config file not found')
    # Check credentials directory
    creds_dir = os.path.join(oc_root, 'credentials')
    if not os.path.isdir(creds_dir):
        issues.append('OAuth credentials directory missing (~/.openclaw/credentials)')
    # Check session transcripts
    sessions_data = _read_json_file(config.SESSIONS_JSON)
    missing = 0
    total = 0
    if isinstance(sessions_data, dict):
        for key, s in sessions_data.items():
            if not isinstance(s, dict):
                continue
            sid = s.get('sessionId', key)
            total += 1
            transcript = os.path.join(config.SESSION_DIR, f'{sid}.jsonl')
            if not os.path.isfile(transcript):
                missing += 1
    if missing > 0:
        issues.append(f'{missing}/{total} sessions are missing transcripts')
    return {'issues': issues, 'issueCount': len(issues)}
