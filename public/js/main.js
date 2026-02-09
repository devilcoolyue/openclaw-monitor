import { S } from './state.js';
import { i18n } from './i18n.js';
import { initTheme, toggleTheme } from './theme.js';
import { initLang, toggleLang } from './lang.js';
import { openSidebar, closeSidebar } from './mobile.js';
import { switchView, loadSessions } from './sessions.js';
import { loadSystem } from './render-system.js';
import { bootCheck } from './boot.js';
import { reRenderLive } from './filter.js';

// Register functions on window for inline onclick handlers
window.switchView = switchView;
window.bootCheck = bootCheck;
window.loadSystem = loadSystem;

function initAutoScroll() {
  const saved = localStorage.getItem('autoScroll');
  if (saved !== null) {
    S.autoScroll = saved === 'true';
  }
  document.getElementById('tog-scroll').classList.toggle('on', S.autoScroll);
}

function fetchVersion() {
  fetch('/api/version').then(r => r.json()).then(d => {
    const el = document.getElementById('sb-version');
    if (el && d.version) el.textContent = 'v' + d.version;
  }).catch(() => {});
}

function bindAll() {
  document.getElementById('btn-live').onclick = () => switchView('live');
  document.getElementById('btn-system').onclick = () => switchView('system');

  document.getElementById('menu-btn').onclick = () => {
    const sidebar = document.querySelector('.sidebar');
    sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
  };
  document.getElementById('sidebar-backdrop').onclick = closeSidebar;

  document.getElementById('ss-toggle').onclick = () => {
    document.getElementById('sess-summary').classList.toggle('ss-expanded');
  };

  document.getElementById('theme-btn').onclick = toggleTheme;
  document.getElementById('lang-btn').onclick = toggleLang;

  document.getElementById('logout-btn').onclick = () => {
    fetch('/api/logout').then(() => location.reload());
  };

  const searchInput = document.getElementById('search-input');
  const searchClear = document.getElementById('search-clear');

  searchInput.addEventListener('input', function() {
    S.searchQuery = this.value;
    searchClear.classList.toggle('show', this.value.length > 0);
    if (S.view === 'live') reRenderLive();
  });

  searchClear.onclick = () => {
    searchInput.value = '';
    S.searchQuery = '';
    searchClear.classList.remove('show');
    if (S.view === 'live') reRenderLive();
  };

  document.querySelectorAll('.fpill').forEach(btn => {
    btn.onclick = () => {
      S.filter = btn.dataset.f;
      document.querySelectorAll('.fpill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (S.view === 'live') reRenderLive();
    };
  });

  document.getElementById('tog-scroll').onclick = function() {
    S.autoScroll = !S.autoScroll;
    localStorage.setItem('autoScroll', S.autoScroll);
    this.classList.toggle('on', S.autoScroll);
    if (S.autoScroll) { const el = document.getElementById('stream'); el.scrollTop = el.scrollHeight; }
  };

  document.getElementById('btn-clr').onclick = () => {
    S.liveLogs = [];
    document.getElementById('evt-cnt').textContent = '0';
    document.getElementById('stream').innerHTML = '';
  };

  const stream = document.getElementById('stream');
  const scrollTopBtn = document.getElementById('scroll-top-btn');
  stream.addEventListener('scroll', () => {
    scrollTopBtn.classList.toggle('show', stream.scrollTop > 200);
  });
  scrollTopBtn.onclick = () => {
    stream.scrollTo({ top: 0, behavior: 'smooth' });
  };
}

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initLang();
  initAutoScroll();
  fetchVersion();
  bindAll();
  bootCheck();
});
