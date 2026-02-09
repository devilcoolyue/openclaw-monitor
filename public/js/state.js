/* ── Global state object ──────────────────────────────── */
export const S = {
  view:        'system', // 'system' | 'live' | sessionId
  filter:      'all',
  autoScroll:  true,
  sessions:    [],
  liveLogs:    [],       // buffer for re-filter
  es:          null,     // current EventSource
  historyDone: false,
  searchQuery: '',       // search query
  theme:       'dark',   // 'dark' | 'light'
  lang:        'zh',     // 'en' | 'zh'
  systemData:  null,
  systemTimer: null,
  sessionsTimer: null,
  gatewayOnline: null,
  healthTimer: null,
};
