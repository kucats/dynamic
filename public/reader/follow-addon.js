/* Optional score follower: no feature/profile fetch or mic until enabled.
 * Enabling persists the UI preference only; a microphone always needs Start. */
(() => {
  if (new URLSearchParams(location.search).has('print')) return;
  let follower = null, loading = null, enabled = false;
  const checkbox = document.getElementById('scoreFollowEnabled');
  const status = document.getElementById('scoreFollowLoad');
  async function enable(on) {
    enabled = on;
    try { localStorage.setItem('dynamic-follow-enabled', on ? '1' : '0'); } catch { /* private browsing */ }
    if (!on) { follower?.disable(); return; }
    if (!window.__dynamic) return;
    try {
      if (!loading) {
        const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = 'follow.css'; document.head.append(css);
        loading = import('./follow.mjs');
      }
      const mod = await loading;
      follower ||= mod.createFollower(window.__dynamic);
      if (enabled) follower.enable();
      status.textContent = 'ローカル処理。マイク開始で聴き始めます。音声は保存・送信しません。';
    } catch {
      loading = null; enabled = false; checkbox.checked = false; follower?.disable();
      try { localStorage.setItem('dynamic-follow-enabled', '0'); } catch { /* optional */ }
      status.textContent = '譜面追従を読み込めませんでした。もう一度有効にしてください。';
    }
  }
  checkbox.onchange = () => enable(checkbox.checked);
  try { checkbox.checked = localStorage.getItem('dynamic-follow-enabled') === '1'; } catch { /* optional */ }
  if (window.__dynamic) enable(checkbox.checked);
  else document.addEventListener('dynamic:ready', () => enable(checkbox.checked), { once: true });
})();
