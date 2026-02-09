import { S } from './state.js';
import { i18n } from './i18n.js';
import { esc, fmtTime, badgeLabel, linkSids, rmEmpty } from './utils.js';
import { showToast } from './toast.js';

export function ensureLogHeader() {
  const stream = document.getElementById('stream');
  let header = stream.querySelector('.log-header');
  if (!header) {
    header = document.createElement('div');
    header.className = 'log-header';
    stream.insertBefore(header, stream.firstChild);
  }
  header.innerHTML = `<span>${i18n('time')}</span><span>${i18n('type')}</span><span>${i18n('content')}</span><span>${i18n('actions')}</span>`;
}

export function appendLogRow(data) {
  const stream = document.getElementById('stream');
  rmEmpty(stream);
  ensureLogHeader();

  const t    = data.type || 'other';
  const ts   = data.timestamp || data.ts || data.time || data['@timestamp'] || (data._meta && data._meta.date) || null;
  const time = fmtTime(ts);
  const rawText = data.raw || '';
  const row  = document.createElement('div');
  row.className = 'log-row';
  row.dataset.raw = rawText;
  row.innerHTML =
    `<span class="lr-time">${time}</span>` +
    `<span class="lr-badge bt-${t}">${badgeLabel(t)}</span>` +
    `<span class="lr-msg">${linkSids(esc(rawText))}</span>` +
    `<div class="lr-actions"><button class="copy-btn" title="Copy log"><span class="icon icon-sm"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg></span></button></div>`;

  row.addEventListener('click', function(e) {
    if (e.target.classList.contains('s-link') || e.target.classList.contains('copy-btn')) return;
    this.classList.toggle('expanded');
  });

  const copyBtn = row.querySelector('.copy-btn');
  copyBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    const text = rawText;
    const btn = this;

    const copySuccess = () => {
      btn.classList.add('copied');
      btn.innerHTML = '<span class="icon icon-sm"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></span>';
      showToast(i18n('copySuccess'));
      setTimeout(() => {
        btn.classList.remove('copied');
        btn.innerHTML = '<span class="icon icon-sm"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg></span>';
      }, 1500);
    };

    const copyFail = () => {
      showToast(i18n('copyFailed'), 'error');
    };

    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(copySuccess).catch(copyFail);
    } else {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      try {
        document.execCommand('copy');
        copySuccess();
      } catch (err) {
        copyFail();
      }
      document.body.removeChild(textarea);
    }
  });

  stream.appendChild(row);

  const rows = stream.querySelectorAll('.log-row');
  if (rows.length > 600) {
    for (let i = 0; i < 100; i++) rows[i].remove();
    S.liveLogs = S.liveLogs.slice(-500);
  }

  if (S.autoScroll) stream.scrollTo({ top: stream.scrollHeight, behavior: 'smooth' });
}
