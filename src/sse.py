"""
SSE helpers and JSON response utilities.
"""

import json


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


def _send_sse_heartbeat(handler):
    """Send an SSE heartbeat comment. Returns False on dead connection."""
    try:
        handler.wfile.write(b': heartbeat\n\n')
        handler.wfile.flush()
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False


def _read_json_file(path):
    """Safely read and parse a JSON file, return None on error."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
