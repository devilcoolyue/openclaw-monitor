import { S } from './state.js';
import { i18n } from './i18n.js';

export function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

export function fmtTime(ts) {
  let d;
  if (ts) {
    d = new Date(ts);
    if (isNaN(d.getTime())) d = new Date();
  } else {
    d = new Date();
  }
  return d.toLocaleTimeString('en-US', { hour12:false, hour:'2-digit', minute:'2-digit', second:'2-digit' });
}

export function fmtTokens(n) {
  if (!n || n === 0) return '0';
  if (n < 1000) return String(n);
  if (n < 1000000) return (n / 1000).toFixed(1) + 'K';
  return (n / 1000000).toFixed(2) + 'M';
}

export function fmtIdleTime(idleSince) {
  if (!idleSince) return i18n('idle');
  const now = Date.now() / 1000;
  const diff = now - idleSince;
  if (diff < 60) return i18n('justNow');
  if (diff < 3600) {
    const mins = Math.floor(diff / 60);
    return i18n('minutesAgo').replace('{0}', mins);
  }
  if (diff < 86400) {
    const hours = Math.floor(diff / 3600);
    return i18n('hoursAgo').replace('{0}', hours);
  }
  const days = Math.floor(diff / 86400);
  return i18n('daysAgo').replace('{0}', days);
}

export const BADGE_LABELS = {
  enqueue:'ENQ', dequeue:'DEQ',
  run_start:'RUN ▶', run_done:'RUN ✓',
  tool_start:'TOOL →', tool_end:'← TOOL',
  session_state:'SESSION', error:'ERROR', warn:'WARN', other:'OTHER'
};

export function badgeLabel(t) { return BADGE_LABELS[t] || t.toUpperCase(); }

/* inline markdown renderer */
export function renderMd(src) {
  src = String(src || '');
  var lines = src.split('\n');
  var html = '';
  var inCode = false, codeBuf = '', codeLang = '';
  var listStack = [];

  function closeList() {
    while (listStack.length) { html += '</li></' + listStack.pop() + '>'; }
  }
  function inline(s) {
    s = esc(s);
    s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2">');
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/__(.+?)__/g, '<strong>$1</strong>');
    s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');
    s = s.replace(/_(.+?)_/g, '<em>$1</em>');
    s = s.replace(/~~(.+?)~~/g, '<del>$1</del>');
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    return s;
  }

  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    if (/^```/.test(line)) {
      if (inCode) {
        html += '<pre><code>' + esc(codeBuf) + '</code></pre>';
        codeBuf = ''; inCode = false;
      } else {
        closeList();
        codeLang = line.replace(/^```/, '').trim();
        inCode = true;
      }
      continue;
    }
    if (inCode) { codeBuf += (codeBuf ? '\n' : '') + line; continue; }
    if (!line.trim()) { closeList(); continue; }
    var hm = line.match(/^(#{1,6})\s+(.+)/);
    if (hm) { closeList(); html += '<h'+hm[1].length+'>' + inline(hm[2]) + '</h'+hm[1].length+'>'; continue; }
    if (/^[-*_]{3,}\s*$/.test(line)) { closeList(); html += '<hr>'; continue; }
    if (/^>\s?/.test(line)) { closeList(); html += '<blockquote>' + inline(line.replace(/^>\s?/, '')) + '</blockquote>'; continue; }
    if (/^\|/.test(line) && /\|$/.test(line.trim())) {
      closeList();
      var tLines = [];
      while (i < lines.length && /^\|/.test(lines[i]) && /\|$/.test(lines[i].trim())) {
        tLines.push(lines[i]); i++;
      }
      i--;
      if (tLines.length >= 2) {
        html += '<table>';
        var hCells = tLines[0].split('|').filter(function(c){return c.trim()!=='';});
        html += '<tr>' + hCells.map(function(c){return '<th>'+inline(c.trim())+'</th>';}).join('') + '</tr>';
        for (var ti = 2; ti < tLines.length; ti++) {
          var cells = tLines[ti].split('|').filter(function(c){return c.trim()!=='';});
          html += '<tr>' + cells.map(function(c){return '<td>'+inline(c.trim())+'</td>';}).join('') + '</tr>';
        }
        html += '</table>';
      }
      continue;
    }
    var ulm = line.match(/^(\s*)([-*+])\s+(.*)/);
    if (ulm) {
      var content = ulm[3];
      if (!listStack.length) { html += '<ul>'; listStack.push('ul'); }
      else { html += '</li>'; }
      html += '<li>' + inline(content);
      continue;
    }
    var olm = line.match(/^(\s*)\d+\.\s+(.*)/);
    if (olm) {
      var content = olm[2];
      if (!listStack.length) { html += '<ol>'; listStack.push('ol'); }
      else { html += '</li>'; }
      html += '<li>' + inline(content);
      continue;
    }
    closeList();
    html += '<p>' + inline(line) + '</p>';
  }

  if (inCode) html += '<pre><code>' + esc(codeBuf) + '</code></pre>';
  closeList();
  return html;
}

export function hlJson(s) {
  return s
    .replace(/&quot;([^&]*?)&quot;\s*:/g, '<span class="jk">&quot;$1&quot;:</span>')
    .replace(/&quot;([^&]*?)&quot;/g,      '<span class="js">&quot;$1&quot;</span>')
    .replace(/\b(\d+\.?\d*)\b/g,          '<span class="jn">$1</span>')
    .replace(/\b(true|false|null)\b/g,    '<span class="jw">$1</span>');
}

/* make UUID session ids clickable in live log messages */
export function linkSids(html) {
  return html.replace(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/gi,
    '<span class="s-link" onclick="switchView(\'$1\')" title="Open session">$1</span>');
}

export function rmEmpty(el) { const e = el.querySelector('.empty'); if (e) e.remove(); }
