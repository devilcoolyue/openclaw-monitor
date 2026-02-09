import { S } from './state.js';
import { i18n } from './i18n.js';
import { esc, renderMd, hlJson, rmEmpty } from './utils.js';

export function appendSessionBlock(data, isLive) {
  const stream = document.getElementById('stream');
  rmEmpty(stream);

  const role   = data.role || 'unknown';
  const blocks = data.blocks || [];
  const div    = document.createElement('div');
  div.className = 'session-msg' + (isLive ? ' live' : '');

  let h = '';

  if (role === 'user') {
    h += `<div class="role-hdr rh-user"><span class="icon icon-sm"><svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></span> ${i18n('user')}</div>`;
    blocks.forEach(b => {
      if (b.type === 'text') h += `<div class="blk-user">
          <div class="user-hdr"><span class="icon icon-sm"><svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></span> ${i18n('user')}</div>
          <div class="user-body">${esc(b.content)}</div>
        </div>`;
    });

  } else if (role === 'assistant') {
    h += `<div class="role-hdr rh-asst"><span class="icon icon-sm"><svg viewBox="0 0 24 24"><path d="M12 2a4 4 0 014 4v1h1a3 3 0 013 3v4a3 3 0 01-3 3h-1v1a4 4 0 01-8 0v-1H7a3 3 0 01-3-3v-4a3 3 0 013-3h1V6a4 4 0 014-4z"/><circle cx="9" cy="11" r="1" fill="currentColor"/><circle cx="15" cy="11" r="1" fill="currentColor"/></svg></span> ${i18n('assistant')}</div>`;
    blocks.forEach(b => {
      if (b.type === 'thinking') {
        h += `<div class="blk-think">
          <div class="think-hdr"><span class="icon icon-sm"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg></span> ${i18n('thinking')} <span style="color:var(--t3);font-size:10px">(${b.content.length} chars)</span></div>
          <div class="think-body"><pre>${esc(b.content)}</pre></div>
        </div>`;
      } else if (b.type === 'tool_call') {
        h += `<div class="blk-tcall">
          <div class="tcall-name"><span class="icon icon-sm"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg></span> ${esc(b.name)} <span class="tid">${esc(b.toolCallId||'')}</span></div>
          <div class="tcall-args">${hlJson(esc(JSON.stringify(b.arguments, null, 2)))}</div>
        </div>`;
      } else if (b.type === 'text') {
        h += `<div class="blk-text">
          <div class="text-hdr"><span class="icon icon-sm"><svg viewBox="0 0 24 24"><path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"/></svg></span> ${i18n('response')}</div>
          <div class="text-body">${renderMd(b.content)}</div>
        </div>`;
      }
    });

  } else if (role === 'toolResult') {
    h += `<div class="role-hdr rh-tool"><span class="icon icon-sm"><svg viewBox="0 0 24 24"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg></span> ${i18n('toolResult')}</div>`;
    blocks.forEach(b => {
      if (b.type === 'tool_result') {
        const txt = typeof b.content === 'string' ? b.content : JSON.stringify(b.content, null, 2);
        h += `<div class="blk-tres"><pre>${esc(txt)}</pre></div>`;
      }
    });

  } else if (role === 'meta') {
    h += `<div class="role-hdr rh-meta"><span class="icon icon-sm"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg></span> ${i18n('meta')}</div>`;
    h += `<div class="blk-meta">${esc(JSON.stringify(data.meta || {}, null, 2))}</div>`;

  } else {
    h += `<div class="blk-meta">${esc(JSON.stringify(data))}</div>`;
  }

  div.innerHTML = h;
  stream.appendChild(div);
  if (S.autoScroll) stream.scrollTop = stream.scrollHeight;
}
