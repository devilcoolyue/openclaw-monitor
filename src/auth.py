"""
Authentication: password verification, session management, login page.
"""

import hashlib
import http.cookies
import json
import os
import secrets
import time

import config

AUTH_SESSIONS = {}  # token → expiry_timestamp


def _load_auth():
    """Load .auth file, return (salt, hash) or None if auth disabled."""
    try:
        with open(config.AUTH_FILE) as f:
            line = f.read().strip()
        if ':' in line:
            salt, h = line.split(':', 1)
            return (salt, h)
    except (OSError, ValueError):
        pass
    return None


def _verify_password(password):
    """Check password against stored salt:hash."""
    creds = _load_auth()
    if not creds:
        return False
    salt, stored_hash = creds
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return secrets.compare_digest(h, stored_hash)


def _create_session():
    """Generate a new session token with TTL."""
    token = secrets.token_hex(32)
    AUTH_SESSIONS[token] = time.time() + config.SESSION_TTL
    return token


def _check_auth(handler):
    """Check if request has a valid session cookie. Returns True if authenticated."""
    cookie_header = handler.headers.get('Cookie', '')
    if not cookie_header:
        return False
    cookies = http.cookies.SimpleCookie()
    try:
        cookies.load(cookie_header)
    except http.cookies.CookieError:
        return False
    morsel = cookies.get(config.COOKIE_NAME)
    if not morsel:
        return False
    token = morsel.value
    expiry = AUTH_SESSIONS.get(token)
    if not expiry:
        return False
    if time.time() > expiry:
        del AUTH_SESSIONS[token]
        return False
    return True


def _auth_status():
    """Determine auth status dynamically. Returns 'disabled', 'enabled', or 'locked'.

    - disabled: no auth configured (never set up)
    - enabled:  .auth file present, normal password auth
    - locked:   auth was configured but .auth file is missing (fail-closed)
    """
    has_auth_file = _load_auth() is not None
    # Auth is required if: env var set by systemd OR sentinel file exists
    auth_required = config.ENV_AUTH_REQUIRED or os.path.exists(config.AUTH_REQUIRED_FILE)

    if has_auth_file:
        return 'enabled'
    if auth_required:
        return 'locked'
    return 'disabled'

LOGIN_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>openclaw monitor — Login</title>
<style>
:root{--bg-0:#0a0e13;--bg-1:#111519;--bg-2:#161b22;--bg-3:#1c2330;--border:#1e2530;--t0:#e6edf3;--t1:#c9d1d9;--t2:#8b949e;--t3:#6e7681;--accent:#58a6ff;--green:#3fb950;--red:#ff7b72}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{font-family:'SF Mono','Fira Code','Consolas','Courier New',monospace;background:var(--bg-0);color:var(--t1);display:flex;align-items:center;justify-content:center}
.login-box{width:340px;background:var(--bg-1);border:1px solid var(--border);border-radius:10px;padding:36px 30px 30px}
.login-logo{font-size:16px;font-weight:700;color:var(--t0);text-align:center;margin-bottom:6px;letter-spacing:-.3px}
.login-logo em{font-style:normal;color:var(--accent)}
.login-sub{font-size:11px;color:var(--t3);text-align:center;margin-bottom:24px}
.login-label{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--t3);font-weight:600;margin-bottom:6px;display:block}
.login-input{width:100%;padding:9px 12px;border-radius:6px;border:1px solid var(--border);background:var(--bg-2);color:var(--t0);font-family:inherit;font-size:13px;outline:none;transition:border-color .15s}
.login-input:focus{border-color:var(--accent)}
.login-btn{width:100%;margin-top:18px;padding:10px;border-radius:6px;border:none;background:var(--accent);color:#fff;font-family:inherit;font-size:13px;font-weight:600;cursor:pointer;transition:opacity .15s}
.login-btn:hover{opacity:.9}
.login-btn:disabled{opacity:.5;cursor:not-allowed}
.login-err{color:var(--red);font-size:11px;text-align:center;margin-top:12px;min-height:16px}
</style>
</head>
<body>
<div class="login-box">
  <div class="login-logo"><em>openclaw</em> monitor</div>
  <div class="login-sub">Authentication required</div>
  <form id="login-form">
    <label class="login-label" for="pw">Password</label>
    <input class="login-input" id="pw" type="password" autocomplete="current-password" autofocus>
    <button class="login-btn" type="submit">Sign In</button>
  </form>
  <div class="login-err" id="err"></div>
</div>
<script>
document.getElementById('login-form').addEventListener('submit', async function(e) {
  e.preventDefault();
  const btn = this.querySelector('button');
  const err = document.getElementById('err');
  btn.disabled = true;
  err.textContent = '';
  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({password: document.getElementById('pw').value})
    });
    const data = await res.json();
    if (data.ok) {
      location.reload();
    } else {
      err.textContent = data.error || 'Invalid password';
      btn.disabled = false;
    }
  } catch(ex) {
    err.textContent = 'Connection error';
    btn.disabled = false;
  }
});
</script>
</body>
</html>'''

LOCKED_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>openclaw monitor — Locked</title>
<style>
:root{--bg-0:#0a0e13;--bg-1:#111519;--border:#1e2530;--t0:#e6edf3;--t1:#c9d1d9;--t2:#8b949e;--t3:#6e7681;--red:#ff7b72;--yellow:#d29922}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{font-family:'SF Mono','Fira Code','Consolas','Courier New',monospace;background:var(--bg-0);color:var(--t1);display:flex;align-items:center;justify-content:center}
.lock-box{width:400px;background:var(--bg-1);border:1px solid var(--red);border-radius:10px;padding:36px 30px 30px}
.lock-icon{font-size:32px;text-align:center;margin-bottom:12px}
.lock-title{font-size:16px;font-weight:700;color:var(--red);text-align:center;margin-bottom:8px}
.lock-msg{font-size:12px;color:var(--t2);text-align:center;line-height:1.6;margin-bottom:20px}
.lock-cmd{background:#0d1117;border:1px solid var(--border);border-radius:6px;padding:12px 14px;font-size:11px;color:var(--yellow);line-height:1.8;word-break:break-all}
</style>
</head>
<body>
<div class="lock-box">
  <div class="lock-icon">&#x1F512;</div>
  <div class="lock-title">System Locked</div>
  <div class="lock-msg">
    Authentication file missing or tampered.<br>
    The system has been locked down for security.<br>
    Re-run the installer to restore access:
  </div>
  <div class="lock-cmd">./scripts/install.sh</div>
</div>
</body>
</html>'''
