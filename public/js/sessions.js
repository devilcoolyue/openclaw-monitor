import { S } from './state.js';
import { i18n } from './i18n.js';
import { fmtTokens, fmtIdleTime, esc } from './utils.js';
import { showToast } from './toast.js';
import { isMobile, closeSidebar } from './mobile.js';
import { closeES, clearStream, setConn } from './connection.js';
import { startLive, startSession } from './sse.js';
import { loadSystem, renderSystem } from './render-system.js';

const _LABEL_I18N = {
  heartbeat: 'sessHeartbeat',
  cron: 'sessCron',
  feishu_group: 'sessFeishuGroup',
  feishu_dm: 'sessFeishuDM',
  ddingtalk_group: 'sessDdingtalkGroup',
  ddingtalk_dm: 'sessDdingtalkDM',
  qqbot_group: 'sessQqbotGroup',
  qqbot_dm: 'sessQqbotDM',
  wecom_group: 'sessWecomGroup',
  wecom_dm: 'sessWecomDM',
  main: 'sessMain',
};

function _sessionLabel(s) {
  const key = _LABEL_I18N[s.labelType];
  if (key) return i18n(key);
  // Generic fallback: parse "{provider}_{dm|group}" for unknown platforms
  const m = s.labelType?.match(/^(.+)_(dm|group)$/);
  if (m) {
    const suffix = m[2] === 'group' ? i18n('sessGroupSuffix') : i18n('sessDmSuffix');
    return m[1] + ' ' + suffix;
  }
  if (s.label) return s.label;
  return s.id.substring(0,8) + '-' + s.id.substring(9,13) + '…';
}

let _sessionsLoading = false;
export async function loadSessions() {
  if (_sessionsLoading) return;
  _sessionsLoading = true;
  try {
    S.sessions = await (await fetch('/api/sessions')).json();
    renderSessions();
    updateSessionSummary();
  } catch(e) { console.error('sessions load:', e); }
  _sessionsLoading = false;
}

export function renderSessions() {
  const el = document.getElementById('sb-sessions');
  if (!S.sessions.length) {
    el.innerHTML = `<div class="empty" style="min-height:100px"><p>${i18n('noSessions')}</p></div>`;
    document.getElementById('sess-active').textContent = '';
    return;
  }
  S.sessions.sort((a, b) => {
    if (a.status === 'processing' && b.status !== 'processing') return -1;
    if (a.status !== 'processing' && b.status === 'processing') return 1;
    return (b.mtime || 0) - (a.mtime || 0);
  });
  const active = S.sessions.filter(s => s.status === 'processing').length;
  document.getElementById('sess-active').textContent = active ? `${active} ${i18n('active')}` : '';

  el.innerHTML = S.sessions.map(s => {
    const label = _sessionLabel(s);
    const shortId = s.id.substring(0,8) + '…';
    const isAct = S.view === s.id;
    const proc  = s.status === 'processing';
    const statusText = proc ? i18n('processing') : fmtIdleTime(s.idle_since);
    return `<div class="s-card${isAct?' active':''}${proc?' processing':''}" data-session="${s.id}" onclick="switchView('${s.id}')">
      <div class="s-card-top">
        <span class="s-card-id">${esc(label)}</span>
        <span class="badge ${proc?'badge-proc':'badge-idle'}">
          ${proc?'<span class="bd"></span>':''}${statusText}
        </span>
      </div>
      <div class="s-card-bot">
        <span>${esc(shortId)} · ${s.message_count||0} ${i18n('msgs')}</span>
        <span>${s.model||'—'}</span>
      </div>
    </div>`;
  }).join('');
}

function updateSessionSummary() {
  const id = S.view;
  if (id === 'live' || id === 'system') return;
  const sess = S.sessions.find(s => s.id === id);
  if (!sess) return;

  document.getElementById('ss-msgs').textContent     = sess.message_count || '—';
  const status = sess.status || 'idle';
  document.getElementById('ss-status').textContent   = status === 'processing' ? i18n('processing') : i18n('idle');

  const usage = sess.usage;
  if (usage && usage.totalTokens > 0) {
    document.getElementById('ss-tokens').textContent = fmtTokens(usage.totalTokens);
    document.getElementById('ss-tokens').title =
      `${i18n('inputTokens')}: ${fmtTokens(usage.input)} | ${i18n('outputTokens')}: ${fmtTokens(usage.output)} | ${i18n('cacheTokens')}: ${fmtTokens(usage.cacheRead)}`;
    if (usage.cost > 0) {
      document.getElementById('ss-cost').textContent = '$' + usage.cost.toFixed(4);
    } else {
      document.getElementById('ss-cost').textContent = '—';
    }
  } else {
    document.getElementById('ss-tokens').textContent = '—';
    document.getElementById('ss-cost').textContent = '—';
  }

  const modelsEl = document.getElementById('ss-models');
  const models = sess.models || {};
  const modelKeys = Object.keys(models);
  if (modelKeys.length > 0) {
    modelsEl.innerHTML = modelKeys.map(m => {
      const u = models[m];
      const isCurrent = m === sess.model;
      const costStr = u.cost > 0 ? ` · $${u.cost.toFixed(4)}` : '';
      const detail = `${fmtTokens(u.totalTokens)}${costStr}`;
      const tooltip = `${i18n('inputTokens')}: ${fmtTokens(u.input)} | ${i18n('outputTokens')}: ${fmtTokens(u.output)} | ${i18n('cacheTokens')}: ${fmtTokens(u.cacheRead)}`;
      return `<span class="ss-model-tag${isCurrent?' current':''}" title="${tooltip}">` +
        `<span class="ss-model-name">${m}</span>` +
        `<span class="ss-model-detail">${detail}</span>` +
        `</span>`;
    }).join('');
  } else {
    modelsEl.innerHTML = `<span class="ss-model-tag current"><span class="ss-model-name">${sess.model||'—'}</span></span>`;
  }

  const statusTxt = (sess.status === 'processing') ? i18n('processing') : i18n('idle');
  const label = _sessionLabel(sess);
  document.getElementById('ss-toggle-info').textContent =
    `${label} · ${sess.model||'—'} · ${statusTxt}`;
}

export function switchView(id) {
  if (isMobile()) closeSidebar();
  closeES();
  if (S.systemTimer) { clearInterval(S.systemTimer); S.systemTimer = null; }
  S.view = id;
  S.historyDone = false;
  clearStream();

  document.querySelectorAll('.nav-btn,.s-card').forEach(e => e.classList.remove('active'));

  if (id === 'live') {
    document.getElementById('btn-live').classList.add('active');
    document.getElementById('mh-title').textContent = i18n('liveLogs');
    document.getElementById('mh-sub').textContent   = 'openclaw logs --follow';
    document.getElementById('filters').style.display = 'flex';
    document.getElementById('search-box').style.display = 'flex';
    document.getElementById('sess-summary').style.display = 'none';
    S.liveLogs = [];
    startLive();
  } else if (id === 'system') {
    document.getElementById('btn-system').classList.add('active');
    document.getElementById('mh-title').textContent = i18n('system');
    document.getElementById('mh-sub').textContent   = 'openclaw system overview';
    document.getElementById('filters').style.display = 'none';
    document.getElementById('search-box').style.display = 'none';
    document.getElementById('sess-summary').style.display = 'none';
    setConn('connected');
    loadSystem();
    S.systemTimer = setInterval(loadSystem, 30000);
  } else {
    const card = document.querySelector(`[data-session="${id}"]`);
    if (card) card.classList.add('active');
    const sess = S.sessions.find(s => s.id === id);

    const label = sess ? _sessionLabel(sess) : id.substring(0,20) + '…';
    document.getElementById('mh-title').textContent = label;
    const modelNames = sess?.models ? Object.keys(sess.models) : [];
    document.getElementById('mh-sub').textContent = sess
      ? (modelNames.length > 0 ? modelNames.join(' / ') : (sess.model || '—'))
      : '';
    document.getElementById('filters').style.display = 'none';
    document.getElementById('search-box').style.display = 'none';

    document.getElementById('sess-summary').style.display = '';
    document.getElementById('ss-id').textContent       = id;
    document.getElementById('ss-provider').textContent = sess?.provider || '—';
    document.getElementById('ss-model').textContent    = sess?.model || '—';

    updateSessionSummary();

    document.getElementById('sess-summary').classList.remove('ss-expanded');

    startSession(id);
  }
}
