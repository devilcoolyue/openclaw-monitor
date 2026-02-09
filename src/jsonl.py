"""
JSONL line parser for session transcript files.
"""

import json


def _parse_jsonl_line(line: str):
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return {'role': 'raw', 'blocks': [{'type': 'text', 'content': line}]}

    if obj.get('type') != 'message':
        return {'role': 'meta', 'blocks': [], 'meta': obj}

    msg         = obj.get('message', {})
    role        = msg.get('role', 'unknown')
    raw_content = msg.get('content', [])
    if isinstance(raw_content, str):
        raw_content = [{'type': 'text', 'text': raw_content}]

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
