"""
Tailscale IP detection.
"""

import subprocess


def _get_tailscale_ip():
    """Detect Tailscale IPv4 address."""
    try:
        r = subprocess.run(['tailscale', 'ip', '-4'],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None
