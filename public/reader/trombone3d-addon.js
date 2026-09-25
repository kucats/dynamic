/* DYNAMIC reader add-on — 3D trombone player (a toy, not a reading aid).
 * Adds a "3D" button to trombone parts. Nothing else (CSS, Three.js, the model) is fetched
 * until the button is pressed. Uses only __dynamic.ext.addNoteHook, so removing this script tag
 * and the trombone3d* files removes the feature. */
(() => {
  'use strict';
  const LEAD_MS = 90;                 // the slide leaves a moment before the note so it lands on the beat
  let R, player = null, loading = null, panel = null, btn = null, open = false, timers = [], lastNote = null;

  const clearTimers = () => { timers.forEach(clearTimeout); timers = []; };
  function show(n) {
    lastNote = n;
    if (!open || !panel) return;
    panel.querySelector('.tb3d-pos b').textContent = n.pos ?? '–';
    player?.setPosition(n.pos);
  }
  function onNote(type, d) {
    if (type === 'select') show(d.note);
    if (!open || !player) return;
    if (type === 'silence') { clearTimers(); player.silence(); return; }
    if (type === 'sound') {
      const { note, delayMs, seconds } = d;
      if (delayMs <= 0) { player.sound(seconds); return; }
      timers.push(setTimeout(() => player?.setPosition(note.pos), Math.max(0, delayMs - LEAD_MS)));
      timers.push(setTimeout(() => player?.sound(seconds), delayMs));
    }
  }

  function buildPanel() {
    const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = 'trombone3d.css'; document.head.append(css);
    panel = document.createElement('section');
    panel.className = 'tb3d'; panel.setAttribute('aria-label', '3Dトロンボーン奏者');
    panel.innerHTML = '<div class="tb3d-h"><span class="tb3d-pos"><small>ポジション</small><b>–</b></span>'
      + '<span class="tb3d-views" role="group" aria-label="視点"><button type="button" data-v="angle" aria-pressed="true">斜め</button><button type="button" data-v="side" aria-pressed="false">横</button><button type="button" data-v="front" aria-pressed="false">正面</button></span>'
      + '<button type="button" class="ghost tb3d-x" aria-label="3D奏者を閉じる">×</button></div>'
      + '<div class="tb3d-stage"><canvas aria-label="3Dトロンボーン奏者（ドラッグで回転）"></canvas><p class="tb3d-msg">読み込み中…</p></div>';
    document.body.append(panel);
    panel.querySelector('.tb3d-x').onclick = () => { setOpen(false); btn.focus(); };
    panel.querySelectorAll('[data-v]').forEach((b) => b.addEventListener('click', () => {
      player?.setView(b.dataset.v);
      panel.querySelectorAll('[data-v]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    }));
  }
  async function setOpen(on) {
    open = on; btn.setAttribute('aria-pressed', String(on));
    if (!panel && on) buildPanel();
    if (panel) panel.hidden = !on;
    document.body.classList.toggle('tb3d-open', on);
    if (!on) { clearTimers(); player?.stop(); document.body.style.removeProperty('--overlay-bottom'); return; }
    document.body.style.setProperty('--overlay-bottom', `${panel.offsetHeight + 16}px`);
    if (!player) {
      try {
        loading = loading || import('./trombone3d.js');
        const mod = await loading;
        player = player || mod.createTrombonePlayer(panel.querySelector('canvas'));
        panel.querySelector('.tb3d-msg').hidden = true;
      } catch (e) {
        loading = null; panel.querySelector('.tb3d-msg').textContent = '3D表示を開始できませんでした（WebGLが必要です）。'; return;
      }
    }
    if (!open) return;
    if (lastNote) { show(lastNote); player.setPosition(lastNote.pos, { immediate: true }); }
    player.start();
  }

  function start() {
    R = window.__dynamic;
    if (!R || !R.ext || R.ext.print || !R.ext.addNoteHook || R.data.instrument !== 'trombone') return;
    btn = document.createElement('button');
    btn.type = 'button'; btn.id = 'tb3dBtn'; btn.className = 'ghost tb3d-launch'; btn.textContent = '3D';
    btn.title = '3Dトロンボーンでスライドの動きを見る'; btn.setAttribute('aria-label', '3Dトロンボーン'); btn.setAttribute('aria-pressed', 'false');
    btn.onclick = () => setOpen(!open);
    // The score button moves into the compact settings sheet on tablet/phone.
    // Keep the 3D entry in the always-visible header so the add-on remains discoverable.
    const links = document.querySelector('.toplinks'), info = document.getElementById('infoBtn');
    if (links) links.insertBefore(btn, info?.parentElement === links ? info : null);
    else {
      const anchor = document.getElementById('scoreBtn');
      anchor ? anchor.after(btn) : document.querySelector('.row1')?.append(btn);
    }
    const cur = R.cur && R.data.notes.find((n) => n.id === R.cur); if (cur) lastNote = cur;
    R.ext.addNoteHook(onNote);
    document.addEventListener('visibilitychange', () => { if (!player || !open) return; if (document.hidden) player.stop(); else player.start(); });
    window.__trombone3d = { get player() { return player; }, get open() { return open; } };
  }
  if (window.__dynamic) start(); else document.addEventListener('dynamic:ready', start, { once: true });
})();
