import { S } from './state.js';
import { appendLogRow } from './render-log.js';

export function filterMatch(type, f) {
  if (f === 'all') return true;
  const map = { queue:['enqueue','dequeue'], run:['run_start','run_done'],
                tool:['tool_start','tool_end'], session:['session_state'], error:['error','warn'] };
  return map[f] && map[f].includes(type);
}

export function searchMatch(text, query) {
  if (!query) return true;
  return text.toLowerCase().includes(query.toLowerCase());
}

export function reRenderLive() {
  const stream = document.getElementById('stream');
  stream.innerHTML = '';
  S.liveLogs.forEach(d => {
    if (filterMatch(d.type, S.filter) && searchMatch(d.raw || '', S.searchQuery)) {
      appendLogRow(d);
    }
  });
}
