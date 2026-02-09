import { S } from './state.js';
import { i18n } from './i18n.js';
import { showToast } from './toast.js';

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
    tag.lastChild.textContent = 'LIVE';
  } else {
    tag.classList.add('offline');
    dot.classList.add('offline');
    tag.lastChild.textContent = i18n('offline');
  }
}

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
      showToast(i18n(online ? 'gatewayOnline' : 'gatewayOffline'), online ? 'success' : 'error');
    }
    S.gatewayOnline = online;
    updateLiveTag(online);
  } catch(e) { /* monitor server itself unreachable */ }
  _healthPolling = false;
}
