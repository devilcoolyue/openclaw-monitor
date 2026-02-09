export function isMobile() { return window.innerWidth <= 768; }

export function openSidebar() {
  document.querySelector('.sidebar').classList.add('open');
  document.getElementById('sidebar-backdrop').classList.add('show');
}

export function closeSidebar() {
  document.querySelector('.sidebar').classList.remove('open');
  document.getElementById('sidebar-backdrop').classList.remove('show');
}
