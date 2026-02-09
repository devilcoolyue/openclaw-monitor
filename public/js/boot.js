import { S } from './state.js';
import { renderSessions, switchView, loadSessions } from './sessions.js';
import { pollHealth } from './connection.js';

export function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function setBootStep(id, state) {
  const el = document.getElementById(id);
  el.className = 'boot-step ' + state;
  const iconEl = el.querySelector('.boot-step-icon');
  if (state === 'done')      iconEl.textContent = '✓';
  else if (state === 'fail') iconEl.textContent = '✕';
}

function updateBootText() {
  document.getElementById('boot-step-proc-text').textContent =
    S.lang === 'zh' ? '检测 openclaw 进程…' : 'Detecting openclaw process…';
  document.getElementById('boot-step-log-text').textContent =
    S.lang === 'zh' ? '探测日志文件位置…' : 'Locating log files…';
  document.getElementById('boot-step-sess-text').textContent =
    S.lang === 'zh' ? '加载会话数据…' : 'Loading sessions…';
}

function updateBootAlertText(health) {
  const titleEl = document.getElementById('boot-alert-title');
  const descEl  = document.getElementById('boot-alert-desc');
  const hintEl  = document.getElementById('boot-alert-hint');
  const retryEl = document.getElementById('boot-retry');

  if (S.lang === 'zh') {
    titleEl.textContent = '未检测到 openclaw';
    descEl.textContent  = 'openclaw 进程未运行或无法访问。';
    hintEl.innerHTML    = '请确保 openclaw 已安装并正在运行：<br><code>openclaw</code>';
    retryEl.textContent = '重试';
  } else {
    titleEl.textContent = 'openclaw not detected';
    descEl.textContent  = 'The openclaw process is not running or not accessible on this server.';
    hintEl.innerHTML    = 'Make sure openclaw is installed and running:<br><code>openclaw</code>';
    retryEl.textContent = 'Retry';
  }
}

export async function bootCheck() {
  if (S.sessionsTimer) { clearInterval(S.sessionsTimer); S.sessionsTimer = null; }
  if (S.healthTimer)   { clearInterval(S.healthTimer);   S.healthTimer = null; }

  const screen   = document.getElementById('boot-screen');
  const spinner  = document.getElementById('boot-spinner');
  const icon     = document.getElementById('boot-icon');
  const progress = document.getElementById('boot-progress');
  const alert    = document.getElementById('boot-alert');
  const info     = document.getElementById('boot-info');

  const isRefresh = sessionStorage.getItem('booted');
  if (isRefresh) {
    screen.classList.add('hidden');
    let health;
    try {
      const res = await fetch('/api/health');
      health = await res.json();
    } catch (e) {
      health = { openclaw_available: false, session_dir_exists: false, today_log_exists: false };
    }
    if (!health.openclaw_available && !health.session_dir_exists) {
      sessionStorage.removeItem('booted');
      return bootCheck();
    }
    try {
      S.sessions = await (await fetch('/api/sessions')).json();
      renderSessions();
    } catch(e) {
      S.sessions = [];
    }
    switchView('system');
    S.sessionsTimer = setInterval(loadSessions, 5000);
    pollHealth();
    S.healthTimer = setInterval(pollHealth, 3000);
    return;
  }

  screen.classList.remove('hidden');
  spinner.className = 'boot-spinner';
  icon.className = 'boot-icon';
  icon.textContent = '';
  alert.classList.remove('show');
  info.classList.remove('show');
  progress.style.width = '0%';
  progress.classList.remove('fail');
  ['boot-step-proc','boot-step-log','boot-step-sess'].forEach(id => {
    const el = document.getElementById(id);
    el.className = 'boot-step';
  });

  updateBootText();

  setBootStep('boot-step-proc', 'active');
  progress.style.width = '15%';
  await sleep(400);

  let health;
  try {
    const res = await fetch('/api/health');
    health = await res.json();
  } catch (e) {
    health = { openclaw_available: false, session_dir_exists: false, today_log_exists: false };
  }

  progress.style.width = '33%';

  if (!health.openclaw_available && !health.session_dir_exists) {
    setBootStep('boot-step-proc', 'fail');
    spinner.className = 'boot-spinner fail';
    icon.className = 'boot-icon show';
    icon.textContent = '✕';
    progress.classList.add('fail');
    progress.style.width = '33%';
    alert.classList.add('show');
    updateBootAlertText(health);
    return;
  }

  setBootStep('boot-step-proc', 'done');
  await sleep(300);

  setBootStep('boot-step-log', 'active');
  progress.style.width = '50%';
  await sleep(400);

  const logExists = health.today_log_exists;
  const sessExists = health.session_dir_exists;

  setBootStep('boot-step-log', 'done');
  progress.style.width = '66%';
  await sleep(300);

  setBootStep('boot-step-sess', 'active');
  progress.style.width = '80%';

  try {
    S.sessions = await (await fetch('/api/sessions')).json();
    renderSessions();
  } catch(e) {
    S.sessions = [];
  }

  setBootStep('boot-step-sess', 'done');
  progress.style.width = '100%';

  info.classList.add('show');
  document.getElementById('boot-info-sess-val').textContent = sessExists ? '✓' : '—';
  document.getElementById('boot-info-log-val').textContent  = logExists  ? '✓' : '—';
  if (health.output) {
    document.getElementById('boot-info-sess-val').textContent = sessExists ? '✓ found' : '✕ missing';
    document.getElementById('boot-info-log-val').textContent  = logExists  ? '✓ found' : '✕ missing';
  }

  spinner.className = 'boot-spinner ok';
  icon.className = 'boot-icon show';
  icon.textContent = '✓';

  await sleep(800);

  sessionStorage.setItem('booted', '1');

  screen.classList.add('hidden');
  switchView('live');
  S.sessionsTimer = setInterval(loadSessions, 5000);
  pollHealth();
  S.healthTimer = setInterval(pollHealth, 3000);
}
