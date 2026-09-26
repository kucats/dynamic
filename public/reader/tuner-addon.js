/* DYNAMIC reader add-on — tuner. Adds a "チューナー" button next to 説明 on every part.
 * Nothing (CSS, tuner.mjs, the microphone) is loaded or opened until the button is pressed.
 * To remove the feature, delete this script tag and the tuner* files. */
(() => {
  'use strict';
  let tuner = null, loading = null, btn = null, open = false;

  async function setOpen(on) {
    open = on; btn.setAttribute('aria-pressed', String(on));
    document.body.classList.toggle('tn-open', on);
    if (!on) { tuner?.close(); return; }
    if (!tuner) {
      try {
        if (!document.querySelector('link[href="tuner.css"]')) {
          const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = 'tuner.css'; document.head.append(css);
        }
        loading = loading || import('./tuner.mjs');
        const mod = await loading;
        tuner = tuner || mod.createTuner({ instrument: window.__dynamic?.data?.instrument, onClose: () => { setOpen(false); btn.focus(); } });
      } catch (e) {
        loading = null; open = false; btn.setAttribute('aria-pressed', 'false'); document.body.classList.remove('tn-open'); return;
      }
    }
    if (open) tuner.open();
  }

  function start() {
    if (new URLSearchParams(location.search).has('print') || document.getElementById('tunerBtn')) return;
    btn = document.createElement('button');
    btn.type = 'button'; btn.id = 'tunerBtn'; btn.className = 'ghost tuner-btn';
    btn.title = 'チューナー（マイクで音程を測る）'; btn.setAttribute('aria-label', 'チューナー'); btn.setAttribute('aria-pressed', 'false');
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M9 2v8.5a3 3 0 0 0 6 0V2M12 13.5V22"/></svg><span>チューナー</span>';
    btn.onclick = () => setOpen(!open);
    const info = document.getElementById('infoBtn');
    info ? info.before(btn) : document.querySelector('.toplinks')?.append(btn);
    window.__tuner = { get tuner() { return tuner; }, get open() { return open; }, close: () => setOpen(false) };
  }
  // The button does not depend on part data, so it appears even while the part is loading.
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true }); else start();
})();
