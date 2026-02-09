import { S } from './state.js';
import { i18n } from './i18n.js';

export function closeES() { if (S.es) { S.es.close(); S.es = null; } }

export function clearStream() {
  document.getElementById('stream').innerHTML =
    `<div class="empty"><div class="ei"></div><p>${i18n('connecting')}</p></div>`;
}

export function setConn(st) {
  document.getElementById('conn-dot').className  = 'cd ' + st;
  document.getElementById('conn-label').textContent =
    st === 'connected' ? i18n('connected') : st === 'disconnected' ? i18n('disconnected') : i18n('connecting');
}

export function updateLiveTag(online) {
  const tag = document.querySelector('.live-tag');
  const dot = document.querySelector('.live-dot');
  if (!tag || !dot) return;
  if (online) {
    tag.classList.remove('offline');
    dot.classList.remove('offline');
    tag.lastChild.textContent = i18n('live');
  } else {
    tag.classList.add('offline');
    dot.classList.add('offline');
    tag.lastChild.textContent = i18n('offline');
  }
}

/* ── Gateway status overlay ────────────────────────────── */
let _gwOverlayAutoTimer = null;

function _showGwOverlay(online) {
  const el = document.getElementById('gw-overlay');
  const ring = document.getElementById('gw-overlay-ring');
  const icon = document.getElementById('gw-overlay-icon');
  const title = document.getElementById('gw-overlay-title');
  const desc = document.getElementById('gw-overlay-desc');

  if (_gwOverlayAutoTimer) { clearTimeout(_gwOverlayAutoTimer); _gwOverlayAutoTimer = null; }

  if (online) {
    el.className = 'gw-overlay show online';
    ring.className = 'gw-ring online';
    icon.innerHTML = '<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>';
    title.textContent = i18n('gatewayOnline');
    desc.textContent = i18n('gatewayRestored');
    _gwOverlayAutoTimer = setTimeout(() => _hideGwOverlay(), 2500);
  } else {
    el.className = 'gw-overlay show offline';
    ring.className = 'gw-ring offline';
    icon.innerHTML = '<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    title.textContent = i18n('gatewayOffline');
    desc.textContent = i18n('gatewayWaiting');
  }
}

function _hideGwOverlay() {
  const el = document.getElementById('gw-overlay');
  el.classList.add('hiding');
  setTimeout(() => { el.className = 'gw-overlay'; }, 350);
}

export function initGwOverlay() {
  document.getElementById('gw-overlay-close').onclick = _hideGwOverlay;
}

/* ── Health polling ────────────────────────────────────── */
let _healthPolling = false;
export async function pollHealth() {
  if (_healthPolling) return;
  _healthPolling = true;
  try {
    const res = await fetch('/api/health');
    const h = await res.json();
    const online = !!h.openclaw_available;
    const prev = S.gatewayOnline;
    if (prev !== null && online !== prev) {
      _showGwOverlay(online);
    }
    S.gatewayOnline = online;
    updateLiveTag(online);
  } catch(e) { /* monitor server itself unreachable */ }
  _healthPolling = false;
}
