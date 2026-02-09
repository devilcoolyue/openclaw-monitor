import { S } from './state.js';
import { setConn } from './connection.js';
import { filterMatch, searchMatch } from './filter.js';
import { appendLogRow } from './render-log.js';
import { appendSessionBlock } from './render-session.js';
import { esc } from './utils.js';

export function startLive() {
  setConn('connecting');
  S.es = new EventSource('/api/logs/stream');

  S.es.addEventListener('log', e => {
    const d = JSON.parse(e.data);
    S.liveLogs.push(d);
    if (filterMatch(d.type, S.filter) && searchMatch(d.raw || '', S.searchQuery)) {
      appendLogRow(d);
    }
    document.getElementById('evt-cnt').textContent = S.liveLogs.length;
  });

  S.es.addEventListener('status', e => {
    const d = JSON.parse(e.data);
    appendLogRow({ type: d.type || 'warn', raw: d.message || '' });
  });

  S.es.onopen  = () => setConn('connected');
  S.es.onerror = () => {
    setConn('disconnected');
    setTimeout(() => { if (S.view==='live') startLive(); }, 3000);
  };
}

export function startSession(sid) {
  setConn('connecting');
  S.es = new EventSource(`/api/session/${sid}/stream`);

  S.es.addEventListener('session_event', e => {
    appendSessionBlock(JSON.parse(e.data), S.historyDone);
  });

  S.es.addEventListener('history_done', () => {
    S.historyDone = true;
    setConn('connected');
  });

  S.es.addEventListener('status', e => {
    const d = JSON.parse(e.data);
    if (d.type === 'error') {
      setConn('disconnected');
      document.getElementById('stream').innerHTML =
        `<div class="empty"><div class="ei" style="animation:none;border:none"><span class="icon" style="font-size:28px;color:var(--red)"><svg viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></span></div><p>${esc(d.message)}</p></div>`;
    }
  });

  S.es.onopen  = () => setConn('connecting');
  S.es.onerror = () => setConn('disconnected');
}
