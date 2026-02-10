"""
Session file scanning, parsing, and info extraction.
"""

import json
import os
import threading
from datetime import datetime

import config
from sse import _read_json_file

# ── Session info cache (by file mtime) ───────────────────
_session_info_cache = {}   # path → (mtime, info_dict)
_session_cache_lock = threading.Lock()


def _load_session_meta() -> dict:
    """Load sessions.json and build sessionId → metadata reverse lookup."""
    data = _read_json_file(config.SESSIONS_JSON)
    if not data or not isinstance(data, dict):
        return {}
    lookup = {}
    for key, val in data.items():
        sid = val.get('sessionId')
        if not sid:
            continue
        origin = val.get('origin', {})
        lookup[sid] = {
            'sessionKey': key,
            'chatType': val.get('chatType', ''),
            'originLabel': origin.get('label', ''),
            'originProvider': origin.get('provider', ''),
            'displayName': val.get('displayName', ''),
        }
    return lookup


def _derive_label(meta: dict) -> tuple:
    """Derive (labelType, label) from session metadata.

    Returns (labelType, label) where label is the fallback display text
    and labelType is used by frontend for i18n mapping.
    """
    key = meta.get('sessionKey', '')
    chat_type = meta.get('chatType', '')
    origin_label = meta.get('originLabel', '')
    origin_provider = meta.get('originProvider', '')
    display_name = meta.get('displayName', '')

    if origin_label == 'heartbeat' or origin_provider == 'heartbeat':
        return ('heartbeat', 'Heartbeat')
    if 'cron:' in key:
        return ('cron', 'Cron Task')
    if 'feishu:' in key or origin_provider == 'feishu':
        if chat_type == 'group':
            return ('feishu_group', 'Feishu Group')
        return ('feishu_dm', 'Feishu DM')
    if key == 'agent:main:main':
        return ('main', 'Main Session')
    if display_name and display_name != '-':
        return ('custom', display_name)
    return ('', '')


def _enrich_with_meta(sessions: list) -> list:
    """Merge metadata labels into session list, dedupe by session id."""
    meta_lookup = _load_session_meta()
    seen_ids = set()
    result = []
    for s in sessions:
        sid = s.get('id', '')
        if not sid or sid in seen_ids:
            continue
        seen_ids.add(sid)
        meta = meta_lookup.get(sid)
        if meta:
            label_type, label = _derive_label(meta)
            s['labelType'] = label_type
            s['label'] = label
        else:
            s['labelType'] = ''
            s['label'] = ''
        # Use firstMsg as fallback if no label derived
        if not s.get('label') and s.get('firstMsg'):
            s['label'] = s['firstMsg']
            s['labelType'] = 'firstMsg'
        result.append(s)
    return result


def _find_session_file(session_id: str):
    """Locate session JSONL file — check SESSION_DIR first, then search ~/.openclaw."""
    path = os.path.join(config.SESSION_DIR, f'{session_id}.jsonl')
    if os.path.isfile(path):
        return path
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
        m = config.UUID_RE.search(line)
        if not m:
            continue
        sid  = m.group(0)
        path = os.path.join(config.SESSION_DIR, f'{sid}.jsonl')
        info = {'id': sid, 'file': path, 'raw_line': line}
        if os.path.isfile(path):
            mtime = os.path.getmtime(path)
            info['mtime'] = mtime
            info.update(_extract_session_info(path, mtime))
        sessions.append(info)
    return _enrich_with_meta(sessions)


def _scan_session_files() -> list:
    if not os.path.isdir(config.SESSION_DIR):
        return []
    entries = []
    for name in os.listdir(config.SESSION_DIR):
        if not name.endswith('.jsonl'):
            continue
        path = os.path.join(config.SESSION_DIR, name)
        sid  = name[:-len('.jsonl')]
        mtime = os.path.getmtime(path)
        info = _extract_session_info(path, mtime)
        info['id']    = sid
        info['file']  = path
        info['mtime'] = mtime
        entries.append(info)
    entries.sort(key=lambda e: e.get('mtime', 0), reverse=True)
    return _enrich_with_meta(entries)


def _extract_session_info(path: str, mtime: float = None) -> dict:
    if mtime is None:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return {'provider': '', 'model': '', 'status': 'idle', 'message_count': 0}

    with _session_cache_lock:
        cached = _session_info_cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1].copy()

    info = {'provider': '', 'model': '', 'status': 'idle', 'message_count': 0}
    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cost = 0.0
    per_model_usage = {}
    current_model = ''
    first_msg = ''
    try:
        with open(path) as f:
            lines = f.readlines()
        info['message_count'] = len(lines)

        last_event_type = None
        last_role = None
        has_tool_result = {}

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

            if info['model']:
                current_model = info['model']

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

                if current_model:
                    if current_model not in per_model_usage:
                        per_model_usage[current_model] = {'input': 0, 'output': 0, 'cacheRead': 0, 'cost': 0.0}
                    pm = per_model_usage[current_model]
                    pm['input'] += u_input
                    pm['output'] += u_output
                    pm['cacheRead'] += u_cache
                    pm['cost'] += u_cost

            last_event_type = obj.get('type', '')
            if last_event_type == 'message':
                msg = obj.get('message', {})
                last_role = msg.get('role', '')
                content = msg.get('content', [])

                if not first_msg and last_role == 'user' and isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'text':
                            txt = (block.get('text') or '').strip()
                            if txt:
                                first_msg = txt[:30]
                                break
                        elif isinstance(block, str) and block.strip():
                            first_msg = block.strip()[:30]
                            break

                if last_role == 'assistant' and isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'toolCall':
                            tool_call_id = block.get('toolCallId', '')
                            if tool_call_id:
                                has_tool_result[tool_call_id] = False

                if last_role == 'toolResult':
                    tool_call_id = msg.get('toolCallId', '')
                    if tool_call_id:
                        has_tool_result[tool_call_id] = True

        pending_tool_calls = [tid for tid, got_result in has_tool_result.items() if not got_result]

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
            info['idle_since'] = mtime

        total_tokens = total_input + total_output + total_cache_read
        if total_tokens > 0:
            info['usage'] = {
                'input': total_input,
                'output': total_output,
                'cacheRead': total_cache_read,
                'totalTokens': total_tokens,
                'cost': round(total_cost, 6)
            }

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

    if first_msg:
        info['firstMsg'] = first_msg

    with _session_cache_lock:
        _session_info_cache[path] = (mtime, info)
    return info
