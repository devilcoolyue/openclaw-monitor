import { S } from './state.js';
import { i18n } from './i18n.js';
import { updateLiveTag } from './connection.js';
import { renderSessions } from './sessions.js';
import { renderSystem } from './render-system.js';
import { renderModels } from './render-models.js';

export function initLang() {
  const saved = localStorage.getItem('lang') || 'zh';
  S.lang = saved;
  applyLang(saved);
}

export function toggleLang() {
  S.lang = S.lang === 'en' ? 'zh' : 'en';
  localStorage.setItem('lang', S.lang);
  applyLang(S.lang);
}

export function applyLang(lang) {
  const btn = document.getElementById('lang-btn');
  btn.textContent = lang === 'en' ? '中' : 'EN';
  btn.title = lang === 'en' ? '切换到中文' : 'Switch to English';
  updateAllText();
}

export function updateAllText() {
  document.querySelector('.sb-label').innerHTML = `${i18n('sessions')} <span id="sess-active" style="color:var(--green);margin-left:6px"></span>`;
  document.querySelector('#btn-live .nb-label').textContent = i18n('liveLogs');
  document.querySelector('#btn-models .nb-label').textContent = i18n('modelSwitch');
  document.querySelector('#btn-system .nb-label').textContent = i18n('system');

  if (S.view === 'live') {
    document.getElementById('mh-title').textContent = i18n('liveLogs');
  } else if (S.view === 'models') {
    document.getElementById('mh-title').textContent = i18n('modelSwitch');
    document.getElementById('mh-sub').textContent = i18n('modelSwitchSub');
  } else if (S.view === 'system') {
    document.getElementById('mh-title').textContent = i18n('system');
  }

  document.getElementById('search-input').placeholder = i18n('searchLogs');

  const filters = document.querySelectorAll('.fpill');
  const filterKeys = ['all', 'queue', 'run', 'tool', 'session', 'error'];
  filters.forEach((btn, i) => {
    if (filterKeys[i]) btn.textContent = i18n(filterKeys[i]);
  });

  document.querySelector('.toggle-wrap span').textContent = i18n('scroll');
  document.getElementById('btn-clr').textContent = i18n('clear');

  const ssLabels = document.querySelectorAll('.ss-label');
  const labelKeys = ['session', 'provider', 'model', 'messages', 'status', 'tokens', 'cost'];
  ssLabels.forEach((el, i) => {
    if (labelKeys[i]) el.textContent = i18n(labelKeys[i]);
  });

  const dot = document.getElementById('conn-dot');
  if (dot.classList.contains('connected')) {
    document.getElementById('conn-label').textContent = i18n('connected');
  } else if (dot.classList.contains('disconnected')) {
    document.getElementById('conn-label').textContent = i18n('disconnected');
  } else {
    document.getElementById('conn-label').textContent = i18n('connecting');
  }

  const waitText = document.getElementById('stream-wait-text');
  if (waitText) waitText.textContent = i18n('waiting');

  updateLiveTag(S.gatewayOnline !== false);

  if (S.view === 'system' && S.systemData) {
    renderSystem(S.systemData);
  }
  if (S.view === 'models' && S.modelsData) {
    renderModels(S.modelsData);
  }

  renderSessions();

  const logHeader = document.querySelector('.log-header');
  if (logHeader) {
    logHeader.innerHTML = `<span>${i18n('time')}</span><span>${i18n('type')}</span><span>${i18n('content')}</span><span>${i18n('actions')}</span>`;
  }
}
