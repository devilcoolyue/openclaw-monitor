import { S } from './state.js';
import { i18n, translateKey } from './i18n.js';
import { esc, fmtTokens } from './utils.js';

export async function loadSystem() {
  const stream = document.getElementById('stream');
  if (!S.systemData) {
    stream.innerHTML = `<div class="empty"><div class="ei"></div><p>${i18n('sysLoading')}</p></div>`;
  }
  try {
    const data = await fetch('/api/system').then(r => r.json());
    S.systemData = data;
    renderSystem(data);
  } catch(e) {
    console.error('system load:', e);
    stream.innerHTML = `<div class="empty"><div class="ei" style="animation:none;border:none"><span class="icon" style="font-size:28px;color:var(--red)"><svg viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></span></div><p>${esc(e.message)}</p></div>`;
  }
}

export function renderSystem(data) {
  const stream = document.getElementById('stream');
  const now = new Date().toLocaleTimeString('en-US', {hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'});

  let h = '';

  h += `<div class="sys-toolbar">`;
  h += `<span class="sys-toolbar-left">${i18n('sysLastUpdate')}: ${now}</span>`;
  h += `<button class="sys-refresh-btn" onclick="loadSystem()"><span class="icon" style="font-size:12px"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg></span> ${i18n('sysRefresh')}</button>`;
  h += `</div>`;

  h += `<div class="sys-grid">`;

  const svgIcon = (d) => `<span class="icon icon-sm"><svg viewBox="0 0 24 24">${d}</svg></span>`;

  h += sysCard(svgIcon('<path d="M1 1l22 22"/><path d="M16.72 11.06A10.94 10.94 0 0119 12.55"/><path d="M5 12.55a10.94 10.94 0 015.17-2.39"/><path d="M10.71 5.05A16 16 0 0122.56 9"/><path d="M1.42 9a15.91 15.91 0 014.7-2.88"/><path d="M8.53 16.11a6 6 0 016.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/>'), i18n('sysChannelHealth'), renderChannelHealth(data.channel_health));
  h += sysCard(svgIcon('<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>'), i18n('sysDiagnostics'), renderDiagnostics(data.diagnostics));
  h += sysCard(svgIcon('<path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/>'), i18n('sysPresence'), renderPresence(data.presence));
  h += sysCard(svgIcon('<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/>'), i18n('sysContextWindow'), renderContextWindow(data.context_window));
  h += sysCard(svgIcon('<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>'), i18n('sysPromptReport'), renderPromptReport(data.system_prompt_report));
  h += sysCard(svgIcon('<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>'), i18n('sysSkillsSnapshot'), renderSkillsSnapshot(data.skills_snapshot));
  h += sysCard(svgIcon('<polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5" rx="1"/><line x1="10" y1="12" x2="14" y2="12"/>'), i18n('sysCompaction'), renderCompaction(data.compaction_history));
  h += sysCard(svgIcon('<rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/>'), i18n('sysDevices'), renderDevices(data.devices));
  h += sysCard(svgIcon('<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'), i18n('sysCronJobs'), renderCronJobs(data.cron_jobs));
  h += sysCard(svgIcon('<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>'), i18n('sysUpdateCheck'), renderUpdateCheck(data.update_check));
  h += sysCard(svgIcon('<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>'), i18n('sysExecApprovals'), renderExecApprovals(data.exec_approvals));

  h += `</div>`;

  stream.innerHTML = h;
}

function sysCard(icon, title, bodyHtml) {
  return `<div class="sys-card">
    <div class="sys-card-hdr"><span class="sys-icon">${icon}</span>${esc(title)}</div>
    <div class="sys-card-body">${bodyHtml}</div>
  </div>`;
}

function renderKvFromObj(obj) {
  if (!obj || typeof obj !== 'object') return `<span class="sys-empty">—</span>`;
  const keys = Object.keys(obj);
  if (keys.length === 0) return `<span class="sys-empty">—</span>`;
  return keys.map(k => {
    let v = obj[k];
    if (typeof v === 'object' && v !== null) v = JSON.stringify(v);
    return `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey(k))}</span><span class="sys-kv-val">${esc(String(v))}</span></div>`;
  }).join('');
}

function renderChannelHealth(data) {
  if (!data) return `<span class="sys-empty">${i18n('sysNoData')}</span>`;
  if (data.error) return `<span class="sys-badge-err">${esc(data.error)}</span>`;
  if (data.raw) return `<div class="sys-pre">${esc(data.raw)}</div>`;
  let h = '';
  if (data.channelSummary && Array.isArray(data.channelSummary)) {
    h += `<div class="sys-section-label">${esc(translateKey('channelSummary'))}</div>`;
    data.channelSummary.forEach(line => {
      const trimmed = (line || '').trim();
      if (!trimmed) return;
      const isConfigured = /configured/i.test(trimmed) && !/not configured/i.test(trimmed);
      const isNotConfigured = /not configured/i.test(trimmed);
      const isSub = trimmed.startsWith('-') || trimmed.startsWith('  ');
      if (isSub) {
        h += `<div class="sys-kv" style="padding-left:16px"><span class="sys-kv-key" style="color:var(--t3)">${esc(trimmed)}</span></div>`;
      } else {
        const badge = isConfigured ? `<span class="sys-badge-ok">${S.lang==='zh'?'已配置':'configured'}</span>`
                    : isNotConfigured ? `<span class="sys-badge-warn">${S.lang==='zh'?'未配置':'not configured'}</span>`
                    : '';
        const name = trimmed.split(':')[0] || trimmed;
        h += `<div class="sys-kv"><span class="sys-kv-key">${esc(name)}</span><span class="sys-kv-val">${badge}</span></div>`;
      }
    });
  }
  if (data.heartbeat) {
    const hb = data.heartbeat;
    h += `<div class="sys-section-label">${esc(translateKey('heartbeat'))}</div>`;
    if (hb.defaultAgentId) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('defaultAgentId'))}</span><span class="sys-kv-val">${esc(hb.defaultAgentId)}</span></div>`;
    if (hb.agents && Array.isArray(hb.agents)) {
      hb.agents.forEach(a => {
        const st = a.enabled ? `<span class="sys-badge-ok">${S.lang==='zh'?'已启用':'enabled'}</span>` : `<span class="sys-badge-warn">${S.lang==='zh'?'已禁用':'disabled'}</span>`;
        h += `<div class="sys-kv"><span class="sys-kv-key">${esc(a.agentId || '—')}</span><span class="sys-kv-val">${st} &nbsp; ${esc(a.every || '')}</span></div>`;
      });
    }
  }
  if (data.gateway) {
    const gw = data.gateway;
    h += `<div class="sys-section-label">${esc(translateKey('gateway'))}</div>`;
    const reachBadge = gw.reachable ? `<span class="sys-badge-ok">${S.lang==='zh'?'可达':'reachable'}</span>` : `<span class="sys-badge-err">${S.lang==='zh'?'不可达':'unreachable'}</span>`;
    h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('status'))}</span><span class="sys-kv-val">${reachBadge}</span></div>`;
    if (gw.mode) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('mode'))}</span><span class="sys-kv-val">${esc(gw.mode)}</span></div>`;
    if (gw.url) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('url'))}</span><span class="sys-kv-val" style="font-size:10px">${esc(gw.url)}</span></div>`;
    if (gw.connectLatencyMs != null) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('connectLatencyMs'))}</span><span class="sys-kv-val">${gw.connectLatencyMs}ms</span></div>`;
    if (gw.self) {
      h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('host'))}</span><span class="sys-kv-val">${esc(gw.self.host || '—')}</span></div>`;
      if (gw.self.ip) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('ip'))}</span><span class="sys-kv-val">${esc(gw.self.ip)}</span></div>`;
    }
    if (gw.error) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('error'))}</span><span class="sys-badge-err">${esc(String(gw.error))}</span></div>`;
  }
  [['gatewayService', data.gatewayService], ['nodeService', data.nodeService]].forEach(([key, svc]) => {
    if (!svc) return;
    h += `<div class="sys-section-label">${esc(translateKey(key))}</div>`;
    const isRunning = /running|active/i.test(svc.runtimeShort || '');
    const badge = isRunning ? `<span class="sys-badge-ok">${esc(svc.runtimeShort)}</span>` : `<span class="sys-badge-warn">${esc(svc.runtimeShort || svc.loadedText || '—')}</span>`;
    h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('runtimeShort'))}</span><span class="sys-kv-val">${badge}</span></div>`;
    if (svc.label) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('type'))}</span><span class="sys-kv-val">${esc(svc.label)}</span></div>`;
  });
  if (data.os) {
    h += `<div class="sys-section-label">${esc(translateKey('os'))}</div>`;
    h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('label'))}</span><span class="sys-kv-val" style="font-size:10px">${esc(data.os.label || data.os.platform || '—')}</span></div>`;
  }
  if (data.update) {
    h += `<div class="sys-section-label">${esc(translateKey('update'))}</div>`;
    if (data.update.installKind) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('installKind'))}</span><span class="sys-kv-val">${esc(data.update.installKind)}</span></div>`;
    if (data.update.packageManager) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('packageManager'))}</span><span class="sys-kv-val">${esc(data.update.packageManager)}</span></div>`;
    if (data.update.registry && data.update.registry.latestVersion) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('latestVersion'))}</span><span class="sys-kv-val"><span class="sys-tag">${esc(data.update.registry.latestVersion)}</span></span></div>`;
    if (data.update.deps) {
      const ds = data.update.deps;
      h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('deps'))}</span><span class="sys-kv-val">${esc(ds.status || '—')}${ds.reason ? ' ('+esc(ds.reason)+')' : ''}</span></div>`;
    }
  }
  if (data.updateChannel) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('updateChannel'))}</span><span class="sys-kv-val"><span class="sys-tag">${esc(data.updateChannel)}</span></span></div>`;
  if (data.memoryPlugin) {
    h += `<div class="sys-section-label">${esc(translateKey('memoryPlugin'))}</div>`;
    const mEnabled = data.memoryPlugin.enabled ? `<span class="sys-badge-ok">${S.lang==='zh'?'已启用':'enabled'}</span>` : `<span class="sys-badge-warn">${S.lang==='zh'?'已禁用':'disabled'}</span>`;
    h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('enabled'))}</span><span class="sys-kv-val">${mEnabled}</span></div>`;
    if (data.memoryPlugin.slot) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('slot'))}</span><span class="sys-kv-val">${esc(data.memoryPlugin.slot)}</span></div>`;
  }
  if (data.agents) {
    h += `<div class="sys-section-label">${esc(translateKey('agents'))}</div>`;
    h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('totalSessions'))}</span><span class="sys-kv-val">${data.agents.totalSessions ?? '—'}</span></div>`;
    if (data.agents.agents && Array.isArray(data.agents.agents)) {
      data.agents.agents.forEach(a => {
        h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('agentId'))}: ${esc(a.id)}</span><span class="sys-kv-val">${a.sessionsCount ?? 0} ${S.lang==='zh'?'个会话':'sessions'}</span></div>`;
      });
    }
  }
  if (data.securityAudit) {
    const sa = data.securityAudit;
    h += `<div class="sys-section-label">${esc(translateKey('securityAudit'))}</div>`;
    if (sa.summary) {
      const s = sa.summary;
      h += `<div style="display:flex;gap:6px;margin-bottom:6px">`;
      if (s.critical) h += `<span class="sys-badge-err">${S.lang==='zh'?'严重':'critical'}: ${s.critical}</span>`;
      if (s.warn) h += `<span class="sys-badge-warn">${S.lang==='zh'?'警告':'warn'}: ${s.warn}</span>`;
      if (s.info) h += `<span class="sys-badge-ok">${S.lang==='zh'?'信息':'info'}: ${s.info}</span>`;
      h += `</div>`;
    }
    if (sa.findings && Array.isArray(sa.findings)) {
      sa.findings.forEach(f => {
        const sevCls = f.severity === 'critical' ? 'err' : f.severity === 'warn' ? 'warn' : 'ok';
        h += `<div style="margin-bottom:4px"><div class="sys-kv"><span class="sys-kv-key" style="flex:1">${esc(f.title)}</span><span class="sys-badge-${sevCls}">${esc(f.severity)}</span></div>`;
        if (f.detail) h += `<div style="font-size:10px;color:var(--t3);padding:2px 0 0 4px;word-break:break-all">${esc(f.detail)}</div>`;
        if (f.remediation) h += `<div style="font-size:10px;color:var(--orange);padding:2px 0 0 4px">${esc(f.remediation)}</div>`;
        h += `</div>`;
      });
    }
  }
  if (data.sessions) {
    h += `<div class="sys-section-label">${esc(translateKey('sessions'))}</div>`;
    h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('count'))}</span><span class="sys-kv-val">${data.sessions.count ?? '—'}</span></div>`;
    if (data.sessions.defaults) {
      const d = data.sessions.defaults;
      if (d.model) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('model'))}</span><span class="sys-kv-val">${esc(d.model)}</span></div>`;
      if (d.contextTokens) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('contextTokens'))}</span><span class="sys-kv-val">${fmtTokens(d.contextTokens)}</span></div>`;
    }
  }
  return h || renderKvFromObj(data);
}

function renderDiagnostics(data) {
  if (!data) return `<span class="sys-empty">${i18n('sysNoData')}</span>`;
  if (data.error) return `<span class="sys-badge-err">${esc(data.error)}</span>`;
  if (data.raw) {
    const lines = data.raw.split('\n').filter(l => l.trim());
    if (lines.length > 0) {
      return lines.map(l => {
        const isPass = /✓|pass|ok/i.test(l);
        const isFail = /✕|✗|fail|error/i.test(l);
        const badge = isPass ? `<span class="sys-badge-ok">${S.lang==='zh'?'通过':'PASS'}</span>`
                    : isFail ? `<span class="sys-badge-err">${S.lang==='zh'?'失败':'FAIL'}</span>`
                    : '';
        return `<div class="sys-kv"><span class="sys-kv-key" style="flex:1">${esc(l.trim())}</span><span class="sys-kv-val">${badge}</span></div>`;
      }).join('');
    }
  }
  if (data.issues && Array.isArray(data.issues)) {
    if (data.issues.length === 0) {
      return `<div class="sys-kv"><span class="sys-kv-key" style="flex:1">${S.lang==='zh'?'未发现问题':'No issues found'}</span><span class="sys-badge-ok">${S.lang==='zh'?'正常':'OK'}</span></div>`;
    }
    let h = `<div class="sys-kv" style="margin-bottom:4px"><span class="sys-kv-key">${esc(translateKey('issueCount'))}</span><span class="sys-badge-warn">${data.issueCount}</span></div>`;
    data.issues.forEach(issue => {
      h += `<div class="sys-kv"><span class="sys-kv-key" style="flex:1;font-size:11px">${esc(issue)}</span><span class="sys-badge-warn">${S.lang==='zh'?'警告':'WARN'}</span></div>`;
    });
    return h;
  }
  return renderKvFromObj(data);
}

function renderPresence(data) {
  if (!data) return `<span class="sys-empty">${i18n('sysNoData')}</span>`;
  if (data.error) return `<span class="sys-badge-err">${esc(data.error)}</span>`;
  if (Array.isArray(data)) {
    if (data.length === 0) return `<span class="sys-empty">${i18n('sysNoData')}</span>`;
    return data.map(p => {
      let h = '';
      if (p.text) h += `<div style="font-size:11px;color:var(--t0);margin-bottom:4px;font-weight:600">${esc(p.text)}</div>`;
      const primary = ['host','ip','version','platform','mode','reason'];
      primary.forEach(k => {
        if (p[k] === undefined) return;
        let val = String(p[k]);
        if (k === 'mode') {
          const badge = p.mode === 'gateway' ? `<span class="sys-badge-ok">${esc(val)}</span>` : `<span class="sys-badge-warn">${esc(val)}</span>`;
          h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey(k))}</span><span class="sys-kv-val">${badge}</span></div>`;
        } else if (k === 'reason') {
          const badge = p.reason === 'self' ? `<span class="sys-badge-ok">${esc(val)}</span>` : `<span class="sys-badge-warn">${esc(val)}</span>`;
          h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey(k))}</span><span class="sys-kv-val">${badge}</span></div>`;
        } else {
          h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey(k))}</span><span class="sys-kv-val">${esc(val)}</span></div>`;
        }
      });
      const secondary = ['deviceFamily','modelIdentifier','deviceId','instanceId'];
      secondary.forEach(k => {
        if (p[k] === undefined) return;
        h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey(k))}</span><span class="sys-kv-val" style="font-size:10px">${esc(String(p[k]))}</span></div>`;
      });
      if (p.roles && Array.isArray(p.roles) && p.roles.length > 0) {
        h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('roles'))}</span><span class="sys-kv-val">${p.roles.map(r => `<span class="sys-tag">${esc(r)}</span>`).join(' ')}</span></div>`;
      }
      if (p.scopes && Array.isArray(p.scopes) && p.scopes.length > 0) {
        h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('scopes'))}</span><span class="sys-kv-val">${p.scopes.map(s => `<span class="sys-tag">${esc(s)}</span>`).join(' ')}</span></div>`;
      }
      if (p.ts) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('ts'))}</span><span class="sys-kv-val">${new Date(p.ts).toLocaleString()}</span></div>`;
      const rendered = new Set([...primary, ...secondary, 'text', 'roles', 'scopes', 'ts']);
      Object.keys(p).forEach(k => { if (!rendered.has(k)) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey(k))}</span><span class="sys-kv-val">${esc(String(p[k]))}</span></div>`; });
      return h;
    }).join('<hr style="border:none;border-top:1px solid var(--border);margin:6px 0">');
  }
  if (data.raw) return `<div class="sys-pre">${esc(data.raw)}</div>`;
  return renderKvFromObj(data);
}

function renderContextWindow(data) {
  if (!data || !Array.isArray(data) || data.length === 0) return `<span class="sys-empty">${i18n('sysNoData')}</span>`;
  return data.map(c => {
    const pct = c.percent != null ? c.percent : 0;
    const cls = pct > 90 ? 'err' : pct > 70 ? 'warn' : 'ok';
    const sid = (c.sessionId || '').substring(0,8) + '…';
    return `<div style="margin-bottom:8px">
      <div class="sys-kv" style="border:none"><span class="sys-kv-key">${sid}</span><span class="sys-kv-val">${pct != null ? pct + '%' : '—'}</span></div>
      <div class="sys-bar"><div class="sys-bar-fill ${cls}" style="width:${pct||0}%"></div></div>
      <div style="font-size:10px;color:var(--t3)">${S.lang==='zh'?'已用':'used'} ${fmtTokens(c.totalTokens||0)} / ${S.lang==='zh'?'总计':'total'} ${fmtTokens(c.contextTokens||0)}</div>
    </div>`;
  }).join('');
}

function renderPromptReport(data) {
  if (!data || !Array.isArray(data) || data.length === 0) return `<span class="sys-empty">${i18n('sysNoData')}</span>`;
  return data.map(r => {
    const sid = (r.sessionId || '').substring(0,8) + '…';
    const report = r.report;
    if (typeof report === 'string') return `<div><strong>${sid}</strong><div class="sys-pre">${esc(report)}</div></div>`;
    if (typeof report === 'object') {
      let h = `<div style="margin-bottom:6px"><strong style="color:var(--t0)">${sid}</strong></div>`;
      if (report.provider) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('provider'))}</span><span class="sys-kv-val">${esc(report.provider)}</span></div>`;
      if (report.model) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('model'))}</span><span class="sys-kv-val">${esc(report.model)}</span></div>`;
      if (report.sandbox) {
        const sbx = report.sandbox;
        h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('sandbox'))}</span><span class="sys-kv-val">${sbx.sandboxed ? `<span class="sys-badge-ok">${esc(sbx.mode)}</span>` : `<span class="sys-badge-warn">${S.lang==='zh'?'关闭':'off'}</span>`}</span></div>`;
      }
      if (report.systemPrompt) {
        const sp = report.systemPrompt;
        h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('systemPrompt'))}</span><span class="sys-kv-val">${sp.chars ?? '—'} ${S.lang==='zh'?'字符':'chars'}</span></div>`;
        if (sp.projectContextChars != null) h += `<div class="sys-kv" style="padding-left:8px"><span class="sys-kv-key" style="color:var(--t3)">${esc(translateKey('projectContextChars'))}</span><span class="sys-kv-val">${sp.projectContextChars}</span></div>`;
        if (sp.nonProjectContextChars != null) h += `<div class="sys-kv" style="padding-left:8px"><span class="sys-kv-key" style="color:var(--t3)">${esc(translateKey('nonProjectContextChars'))}</span><span class="sys-kv-val">${sp.nonProjectContextChars}</span></div>`;
      }
      if (report.injectedWorkspaceFiles && Array.isArray(report.injectedWorkspaceFiles)) {
        h += `<div class="sys-section-label">${esc(translateKey('injectedWorkspaceFiles'))}</div>`;
        report.injectedWorkspaceFiles.forEach(f => {
          const st = f.missing ? `<span class="sys-badge-warn">${S.lang==='zh'?'缺失':'missing'}</span>` : f.truncated ? `<span class="sys-badge-warn">${S.lang==='zh'?'已截断':'truncated'}</span>` : `<span class="sys-badge-ok">${f.injectedChars} ${S.lang==='zh'?'字符':'chars'}</span>`;
          h += `<div class="sys-kv"><span class="sys-kv-key">${esc(f.name)}</span><span class="sys-kv-val">${st}</span></div>`;
        });
      }
      if (report.skills && report.skills.entries) {
        h += `<div class="sys-section-label">${esc(translateKey('skills'))}</div>`;
        h += `<div style="display:flex;flex-wrap:wrap;gap:2px">`;
        report.skills.entries.forEach(s => { h += `<span class="sys-tag">${esc(s.name)}</span>`; });
        h += `</div>`;
      }
      if (report.tools && report.tools.entries) {
        h += `<div class="sys-section-label">${esc(translateKey('tools'))}</div>`;
        h += `<div style="display:flex;flex-wrap:wrap;gap:2px">`;
        report.tools.entries.forEach(t => { h += `<span class="sys-tag">${esc(t.name)}</span>`; });
        h += `</div>`;
      }
      return h;
    }
    return '';
  }).join('<hr style="border:none;border-top:1px solid var(--border);margin:6px 0">');
}

function renderSkillsSnapshot(data) {
  if (!data || !Array.isArray(data) || data.length === 0) return `<span class="sys-empty">${i18n('sysNoData')}</span>`;
  return data.map(entry => {
    const sid = (entry.sessionId || '').substring(0,8) + '…';
    const snap = entry.snapshot;
    if (!snap) return '';
    let names = [];
    if (typeof snap === 'object' && snap.prompt) {
      names = [...snap.prompt.matchAll(/<name>([^<]+)<\/name>/g)].map(m => m[1]);
    } else if (Array.isArray(snap)) {
      names = snap.map(s => typeof s === 'string' ? s : s.name || JSON.stringify(s));
    }
    if (names.length === 0) return '';
    let h = `<div style="margin-bottom:6px"><strong style="color:var(--t0)">${sid}</strong> <span style="font-size:10px;color:var(--t3)">(${names.length})</span></div>`;
    h += `<div style="display:flex;flex-wrap:wrap;gap:2px">`;
    names.forEach(n => { h += `<span class="sys-tag">${esc(n)}</span>`; });
    h += `</div>`;
    return h;
  }).filter(Boolean).join('<hr style="border:none;border-top:1px solid var(--border);margin:6px 0">') || `<span class="sys-empty">${i18n('sysNoData')}</span>`;
}

function renderCompaction(data) {
  if (!data || !Array.isArray(data) || data.length === 0) return `<span class="sys-empty">${i18n('sysNoData')}</span>`;
  return data.map(c => {
    const sid = (c.sessionId || '').substring(0,8) + '…';
    const cnt = c.compactionCount || 0;
    return `<div class="sys-kv"><span class="sys-kv-key">${sid}</span><span class="sys-kv-val">${cnt} ${i18n('sysCompactions')}</span></div>`;
  }).join('');
}

function renderDevices(data) {
  if (!data) return `<span class="sys-empty">${i18n('sysNoData')}</span>`;
  let h = '';
  const paired = data.paired;
  const pending = data.pending;
  if (paired && typeof paired === 'object') {
    const devs = Object.values(paired);
    if (devs.length > 0) {
      h += `<div style="font-size:10px;font-weight:600;color:var(--t2);margin-bottom:4px;text-transform:uppercase;letter-spacing:.5px">${i18n('sysPaired')} (${devs.length})</div>`;
      devs.forEach(d => {
        h += `<div style="margin-bottom:6px;padding:6px 0;border-bottom:1px solid var(--border)">`;
        if (d.platform) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('platform'))}</span><span class="sys-kv-val">${esc(d.platform)}</span></div>`;
        if (d.clientId) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('clientId'))}</span><span class="sys-kv-val">${esc(d.clientId)}</span></div>`;
        if (d.clientMode) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('clientMode'))}</span><span class="sys-kv-val">${esc(d.clientMode)}</span></div>`;
        if (d.role) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('role'))}</span><span class="sys-kv-val">${esc(d.role)}</span></div>`;
        if (d.roles && Array.isArray(d.roles)) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('roles'))}</span><span class="sys-kv-val">${d.roles.map(r => `<span class="sys-tag">${esc(r)}</span>`).join(' ')}</span></div>`;
        if (d.scopes && Array.isArray(d.scopes)) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('scopes'))}</span><span class="sys-kv-val">${d.scopes.map(s => `<span class="sys-tag">${esc(s)}</span>`).join(' ')}</span></div>`;
        if (d.tokens) {
          const tok = Object.values(d.tokens)[0];
          if (tok && tok.lastUsedAtMs) {
            h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('lastUsedAtMs'))}</span><span class="sys-kv-val">${new Date(tok.lastUsedAtMs).toLocaleString()}</span></div>`;
          }
        }
        h += `</div>`;
      });
    } else {
      h += `<div style="font-size:10px;color:var(--t3)">${i18n('sysPaired')}: 0</div>`;
    }
  }
  if (pending && typeof pending === 'object') {
    const pkeys = Object.keys(pending);
    if (pkeys.length > 0) {
      h += `<div style="font-size:10px;font-weight:600;color:var(--orange);margin:6px 0 4px;text-transform:uppercase;letter-spacing:.5px">${i18n('sysPending')} (${pkeys.length})</div>`;
      pkeys.forEach(k => {
        h += `<div class="sys-kv"><span class="sys-kv-key">${esc(k.substring(0,12))}…</span><span class="sys-badge-warn">${i18n('sysPending')}</span></div>`;
      });
    }
  }
  return h || `<span class="sys-empty">${i18n('sysNoData')}</span>`;
}

function renderCronJobs(data) {
  if (!data) return `<span class="sys-empty">${i18n('sysNoData')}</span>`;
  const jobs = data.jobs;
  if (!jobs || !Array.isArray(jobs) || jobs.length === 0) return `<span class="sys-empty">${i18n('sysNoJobs')}</span>`;
  return jobs.map(j => {
    let h = '';
    Object.keys(j).forEach(k => {
      h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey(k))}</span><span class="sys-kv-val">${esc(String(j[k]))}</span></div>`;
    });
    return h;
  }).join('<hr style="border:none;border-top:1px solid var(--border);margin:6px 0">');
}

function renderUpdateCheck(data) {
  if (!data) return `<span class="sys-empty">${i18n('sysNoData')}</span>`;
  let h = '';
  if (data.lastNotifiedVersion) h += `<div class="sys-kv"><span class="sys-kv-key">${i18n('sysVersion')}</span><span class="sys-kv-val">${esc(data.lastNotifiedVersion)}</span></div>`;
  if (data.lastNotifiedTag) h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('lastNotifiedTag'))}</span><span class="sys-kv-val"><span class="sys-tag">${esc(data.lastNotifiedTag)}</span></span></div>`;
  if (data.lastCheckedAt) h += `<div class="sys-kv"><span class="sys-kv-key">${i18n('sysLastChecked')}</span><span class="sys-kv-val">${new Date(data.lastCheckedAt).toLocaleString()}</span></div>`;
  return h || `<span class="sys-empty">${i18n('sysNoData')}</span>`;
}

function renderExecApprovals(data) {
  if (!data) return `<span class="sys-empty">${i18n('sysNoData')}</span>`;
  let h = '';
  if (data.version !== undefined) h += `<div class="sys-kv"><span class="sys-kv-key">${i18n('sysVersion')}</span><span class="sys-kv-val">${data.version}</span></div>`;
  if (data.socket) {
    h += `<div class="sys-kv"><span class="sys-kv-key">${i18n('sysSocket')}</span><span class="sys-kv-val" style="font-size:10px">${esc(data.socket.path || '—')}</span></div>`;
  }
  const agentCount = data.agents ? Object.keys(data.agents).length : 0;
  const defaultCount = data.defaults ? Object.keys(data.defaults).length : 0;
  h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('agents'))}</span><span class="sys-kv-val">${agentCount}</span></div>`;
  h += `<div class="sys-kv"><span class="sys-kv-key">${esc(translateKey('defaults'))}</span><span class="sys-kv-val">${defaultCount}</span></div>`;
  return h;
}
