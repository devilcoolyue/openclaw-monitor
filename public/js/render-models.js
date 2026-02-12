import { S } from './state.js';
import { i18n } from './i18n.js';
import { esc } from './utils.js';
import { showToast } from './toast.js';
import { setConn } from './connection.js';

async function _fetchJsonOrThrow(url, init) {
  const res = await fetch(url, init);
  const raw = await res.text();

  let data = null;
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch (_) {
    const t = raw.trim();
    const looksHtml = t.startsWith('<!DOCTYPE') || t.startsWith('<html') || t.startsWith('<');
    throw new Error(looksHtml ? i18n('modelApiHtmlHint') : i18n('modelApiInvalidJson'));
  }

  if (!res.ok || data.ok === false) {
    throw new Error(data?.error || `HTTP ${res.status}`);
  }

  return data;
}

function _errorHtml(msg) {
  return `<div class="empty"><div class="ei" style="animation:none;border:none"><span class="icon" style="font-size:28px;color:var(--red)"><svg viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></span></div><p>${esc(msg)}</p></div>`;
}

function _modelOptionLabel(opt) {
  const name = opt.name && opt.name !== opt.modelId ? ` (${opt.name})` : '';
  return `${opt.provider}/${opt.modelId}${name}`;
}

function _setSwitchStepState(stepEl, state) {
  if (!stepEl) return;
  stepEl.className = `model-switch-step ${state}`;

  const stateEl = stepEl.querySelector('.model-switch-step-state');
  if (!stateEl) return;

  const key = state === 'active'
    ? 'modelSwitchStepRunning'
    : state === 'done'
      ? 'modelSwitchStepDone'
      : state === 'fail'
        ? 'modelSwitchStepFailed'
        : 'modelSwitchStepPending';
  stateEl.textContent = i18n(key);
}

function _setSwitchProgress(progressBox, fillEl, pctEl, percent, failed = false) {
  if (!progressBox || !fillEl) return;
  const safePercent = Math.max(0, Math.min(100, Number(percent) || 0));
  fillEl.style.width = `${safePercent}%`;
  progressBox.classList.toggle('fail', !!failed);
  if (pctEl) pctEl.textContent = `${Math.round(safePercent)}%`;
}

function _inferFailedStep(msg) {
  const text = String(msg || '').toLowerCase();
  if (text.includes('write config') || text.includes('failed to write config') || text.includes('写入配置')) {
    return 'write';
  }
  if (text.includes('restart') || text.includes('gateway') || text.includes('重启')) {
    return 'restart';
  }
  return '';
}

function _bindEvents(data) {
  const select = document.getElementById('model-select');
  const btn = document.getElementById('model-switch-btn');
  const status = document.getElementById('model-switch-status');
  const refreshBtn = document.getElementById('model-refresh-btn');
  const modal = document.getElementById('model-switch-modal');
  const progressBox = document.getElementById('model-switch-progress');
  const progressFill = document.getElementById('model-switch-progress-fill');
  const progressPct = document.getElementById('model-switch-progress-pct');
  const stepWrite = document.getElementById('model-switch-step-write');
  const stepRestart = document.getElementById('model-switch-step-restart');

  if (refreshBtn) {
    refreshBtn.onclick = () => {
      S.modelsData = null;
      loadModels();
    };
  }

  if (!select || !btn || !status) return;

  const updateDisabled = () => {
    btn.disabled = !select.value ||
      (data.current && select.value.toLowerCase() === String(data.current).toLowerCase());
  };

  const showModal = () => {
    if (!modal) return;
    modal.hidden = false;
    requestAnimationFrame(() => modal.classList.add('show'));
  };

  const hideModal = () => {
    if (!modal) return;
    modal.classList.remove('show');
    setTimeout(() => {
      if (!modal.classList.contains('show')) modal.hidden = true;
    }, 220);
  };

  const resetProgress = () => {
    if (modal) {
      modal.classList.remove('show');
      modal.hidden = true;
    }
    _setSwitchStepState(stepWrite, 'pending');
    _setSwitchStepState(stepRestart, 'pending');
    _setSwitchProgress(progressBox, progressFill, progressPct, 0, false);
  };

  resetProgress();
  select.onchange = updateDisabled;
  updateDisabled();

  btn.onclick = async () => {
    const target = select.value;
    if (!target) {
      showToast(i18n('modelSwitchSelectFirst'), 'error');
      return;
    }

    btn.disabled = true;
    select.disabled = true;
    status.textContent = i18n('modelSwitching');
    status.className = 'model-switch-status';
    showModal();
    _setSwitchStepState(stepWrite, 'active');
    _setSwitchStepState(stepRestart, 'pending');
    _setSwitchProgress(progressBox, progressFill, progressPct, 18, false);

    let autoAdvance = false;
    const autoAdvanceTimer = setTimeout(() => {
      autoAdvance = true;
      _setSwitchStepState(stepWrite, 'done');
      _setSwitchStepState(stepRestart, 'active');
      _setSwitchProgress(progressBox, progressFill, progressPct, 72, false);
    }, 650);

    try {
      const body = await _fetchJsonOrThrow('/api/models/switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target }),
      });
      clearTimeout(autoAdvanceTimer);

      _setSwitchStepState(stepWrite, 'done');
      if (!autoAdvance) {
        _setSwitchStepState(stepRestart, 'active');
        _setSwitchProgress(progressBox, progressFill, progressPct, 72, false);
        await new Promise(resolve => setTimeout(resolve, 160));
      }
      _setSwitchStepState(stepRestart, 'done');
      _setSwitchProgress(progressBox, progressFill, progressPct, 100, false);
      await new Promise(resolve => setTimeout(resolve, 260));
      hideModal();

      const switched = body.changed ? i18n('modelSwitchDone') : i18n('modelAlreadyCurrent');
      status.textContent = switched;
      status.className = 'model-switch-status ok';
      showToast(switched, 'success');

      if (body.gatewayRestarted) {
        showToast(i18n('modelGatewayRestarted'), 'success');
      }

      setConn('connecting');
      S.modelsData = null;
      await loadModels();
    } catch (e) {
      clearTimeout(autoAdvanceTimer);
      const msg = e?.message || i18n('modelSwitchFailed');
      const failedStep = _inferFailedStep(msg);

      if (failedStep === 'restart' || autoAdvance) {
        _setSwitchStepState(stepWrite, 'done');
        _setSwitchStepState(stepRestart, 'fail');
        _setSwitchProgress(progressBox, progressFill, progressPct, 72, true);
      } else {
        _setSwitchStepState(stepWrite, 'fail');
        _setSwitchStepState(stepRestart, 'pending');
        _setSwitchProgress(progressBox, progressFill, progressPct, 22, true);
      }

      status.textContent = msg;
      status.className = 'model-switch-status err';
      showToast(msg, 'error');
      await new Promise(resolve => setTimeout(resolve, 1000));
      hideModal();
    } finally {
      select.disabled = false;
      updateDisabled();
    }
  };
}

export async function loadModels() {
  const stream = document.getElementById('stream');
  if (!S.modelsData) {
    stream.innerHTML = `<div class="empty"><div class="ei"></div><p>${i18n('modelLoading')}</p></div>`;
  }

  try {
    const data = await _fetchJsonOrThrow('/api/models');
    S.modelsData = data;
    renderModels(data);
  } catch (e) {
    console.error('models load:', e);
    stream.innerHTML = _errorHtml(e?.message || i18n('modelLoadFailed'));
  }
}

export function renderModels(data) {
  const stream = document.getElementById('stream');
  if (!data) {
    stream.innerHTML = _errorHtml(i18n('modelLoadFailed'));
    return;
  }

  const options = Array.isArray(data.options) ? data.options : [];
  const optionHtml = options.length
    ? options.map(opt => {
      const selected = data.current && String(opt.value).toLowerCase() === String(data.current).toLowerCase()
        ? ' selected'
        : '';
      return `<option value="${esc(opt.value)}"${selected}>${esc(_modelOptionLabel(opt))}</option>`;
    }).join('')
    : `<option value="">${esc(i18n('modelNoOptions'))}</option>`;

  let h = '';
  h += `<div class="sys-toolbar">`;
  h += `<span class="sys-toolbar-left">${esc(i18n('modelConfigPath'))}: ${esc(data.configPath || '—')}</span>`;
  h += `<button class="sys-refresh-btn" id="model-refresh-btn"><span class="icon" style="font-size:12px"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg></span>${esc(i18n('sysRefresh'))}</button>`;
  h += `</div>`;

  h += `<div class="model-page">`;
  h += `  <div class="model-card">`;
  h += `    <div class="model-card-hdr">${esc(i18n('modelCurrent'))}</div>`;
  h += `    <div class="model-card-body">`;
  h += `      <div class="model-current">${esc(data.current || '—')}</div>`;
  h += `      <div class="model-help">${esc(i18n('modelCurrentHint'))}</div>`;
  h += `    </div>`;
  h += `  </div>`;

  h += `  <div class="model-card">`;
  h += `    <div class="model-card-hdr">${esc(i18n('modelSelectTarget'))}</div>`;
  h += `    <div class="model-card-body">`;
  h += `      <label class="model-label" for="model-select">${esc(i18n('modelAvailable'))}</label>`;
  h += `      <select id="model-select" class="model-select">${optionHtml}</select>`;
  h += `      <div class="model-actions">`;
  h += `        <button id="model-switch-btn" class="model-switch-btn">${esc(i18n('modelSwitchBtn'))}</button>`;
  h += `      </div>`;
  h += `      <div class="model-help">${esc(i18n('modelSwitchHint'))}</div>`;
  h += `      <div id="model-switch-status" class="model-switch-status"></div>`;
  h += `    </div>`;
  h += `  </div>`;

  h += `  <div class="model-card">`;
  h += `    <div class="model-card-hdr">${esc(i18n('modelAllOptions'))} (${options.length})</div>`;
  h += `    <div class="model-card-body">`;
  if (options.length) {
    h += `      <div class="model-tags">`;
    options.forEach(opt => {
      const currentCls = data.current && String(opt.value).toLowerCase() === String(data.current).toLowerCase()
        ? ' current'
        : '';
      h += `        <span class="model-tag${currentCls}">${esc(_modelOptionLabel(opt))}</span>`;
    });
    h += `      </div>`;
  } else {
    h += `      <div class="sys-empty">${esc(i18n('modelNoOptions'))}</div>`;
  }
  h += `    </div>`;
  h += `  </div>`;
  h += `</div>`;
  h += `<div id="model-switch-modal" class="model-switch-modal" hidden>`;
  h += `  <div class="model-switch-modal-box" role="dialog" aria-modal="true" aria-live="polite">`;
  h += `    <div class="model-switch-modal-title">${esc(i18n('modelSwitchProgressTitle'))}</div>`;
  h += `    <div id="model-switch-progress" class="model-switch-progress">`;
  h += `      <div class="model-switch-progress-hdr">`;
  h += `        <span>${esc(i18n('modelSwitching'))}</span>`;
  h += `        <span id="model-switch-progress-pct" class="model-switch-progress-pct">0%</span>`;
  h += `      </div>`;
  h += `      <div class="model-switch-progress-track"><div id="model-switch-progress-fill" class="model-switch-progress-fill"></div></div>`;
  h += `      <div class="model-switch-steps">`;
  h += `        <div id="model-switch-step-write" class="model-switch-step pending">`;
  h += `          <span class="model-switch-step-icon">1</span>`;
  h += `          <span class="model-switch-step-label">${esc(i18n('modelSwitchStepWrite'))}</span>`;
  h += `          <span class="model-switch-step-state">${esc(i18n('modelSwitchStepPending'))}</span>`;
  h += `        </div>`;
  h += `        <div id="model-switch-step-restart" class="model-switch-step pending">`;
  h += `          <span class="model-switch-step-icon">2</span>`;
  h += `          <span class="model-switch-step-label">${esc(i18n('modelSwitchStepRestart'))}</span>`;
  h += `          <span class="model-switch-step-state">${esc(i18n('modelSwitchStepPending'))}</span>`;
  h += `        </div>`;
  h += `      </div>`;
  h += `    </div>`;
  h += `  </div>`;
  h += `</div>`;

  stream.innerHTML = h;
  _bindEvents(data);
}
