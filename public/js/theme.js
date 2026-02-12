import { S } from './state.js';

const THEME_BG = {
  dark: '#0a0e13',
  light: '#f6f8fa'
};

const THEME_TRANSITION_MS = 1400;

let _isThemeAnimating = false;

export function initTheme() {
  const saved = localStorage.getItem('theme') || 'dark';
  S.theme = saved;
  applyTheme(saved);
}

export function toggleTheme() {
  if (_isThemeAnimating) return;

  const nextTheme = S.theme === 'dark' ? 'light' : 'dark';
  const { x, y } = _getThemeOrigin();
  const r = _getThemeRadius(x, y);

  _setThemeTransitionVars(x, y, r);

  S.theme = nextTheme;
  localStorage.setItem('theme', nextTheme);

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    applyTheme(nextTheme);
    return;
  }

  if (typeof document.startViewTransition === 'function') {
    _isThemeAnimating = true;
    const vt = document.startViewTransition(() => {
      applyTheme(nextTheme);
    });
    vt.finished.finally(() => {
      _isThemeAnimating = false;
    });
    return;
  }

  _isThemeAnimating = true;
  _runFallbackRipple(nextTheme, x, y, r);
}

export function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.getElementById('theme-icon');
  if (theme === 'dark') {
    icon.innerHTML = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
  } else {
    icon.innerHTML = '<svg viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1111.21 3a7 7 0 009.79 9.79z"/></svg>';
  }
  document.getElementById('theme-btn').title = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';
}

function _getThemeOrigin() {
  const btn = document.getElementById('theme-btn');
  if (!btn) {
    return { x: 36, y: window.innerHeight - 36 };
  }
  const rect = btn.getBoundingClientRect();
  return {
    x: rect.left + rect.width / 2,
    y: rect.top + rect.height / 2
  };
}

function _getThemeRadius(x, y) {
  const maxX = Math.max(x, window.innerWidth - x);
  const maxY = Math.max(y, window.innerHeight - y);
  return Math.hypot(maxX, maxY);
}

function _setThemeTransitionVars(x, y, r) {
  const root = document.documentElement;
  root.style.setProperty('--theme-transition-x', `${x}px`);
  root.style.setProperty('--theme-transition-y', `${y}px`);
  root.style.setProperty('--theme-transition-r', `${r}px`);
}

function _runFallbackRipple(nextTheme, x, y, r) {
  const overlay = document.createElement('div');
  overlay.className = 'theme-ripple-overlay';
  overlay.style.setProperty('--theme-transition-x', `${x}px`);
  overlay.style.setProperty('--theme-transition-y', `${y}px`);
  overlay.style.setProperty('--theme-transition-r', `${r}px`);
  overlay.style.background = THEME_BG[nextTheme] || THEME_BG.dark;

  document.body.appendChild(overlay);

  requestAnimationFrame(() => {
    overlay.classList.add('is-active');
  });

  let applied = false;
  let finalized = false;
  const applyNextTheme = () => {
    if (applied) return;
    applied = true;
    applyTheme(nextTheme);
  };

  const finalize = () => {
    if (finalized) return;
    finalized = true;
    applyNextTheme();
    overlay.remove();
    _isThemeAnimating = false;
  };

  window.setTimeout(finalize, THEME_TRANSITION_MS + 200);
  overlay.addEventListener('transitionend', finalize, { once: true });
}
