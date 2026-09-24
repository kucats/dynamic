/* DYNAMIC 譜読みアプリ — practice memos (per signed-in user, per part).
 * Kept apart from app.js: it only uses the small `__dynamic.ext` hook surface.
 * Storage and timestamps live on the Worker (/api/memos/<part>); see docs/reader-memos.md. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const KIND_LABEL = { note: 'メモ', issue: '課題', good: 'できた' };
  const M = { enabled: false, loggedIn: false, email: '', memos: [], pen: false, editing: null, anchor: null, busy: false };
  let R, X, D;   // reader API, its ext hooks, part data

  const fmtTime = (iso) => { try { return new Date(iso).toLocaleString('ja-JP', { dateStyle: 'medium', timeStyle: 'short' }); } catch (e) { return iso; } };
  const mvtOrder = (k) => { const i = D.movements.findIndex((m) => m.key === k); return i < 0 ? 99 : i; };
  function memoLabel(memo) {
    const a = memo.anchor || {};
    return `${X.mvNum[a.mvt] || a.mvt}楽章${a.bar ? ` ${a.bar}小節` : ''}${memo.rehearsal ? ` · 練習記号${memo.rehearsal}` : ''}`;
  }

  // ---------- anchors ----------
  function barAt(sy, x) {                 // printed bar under an image x (first bar of a multi-rest)
    let best = null, dist = Infinity;
    for (const [xa, xb, lab] of sy.segs) {
      if (!lab) continue;
      const d = x < xa ? xa - x : x >= xb ? x - xb + 1 : 0;
      if (d < dist) { dist = d; best = X.segRange(lab)[0]; }
    }
    return best;
  }
  /** Where to draw a memo: its own staff when page/system still match, else the start of its bar. */
  function memoPos(memo) {
    const a = memo.anchor || {};
    let sy = D.systems.find((s) => s.mvt === a.mvt && s.page === a.page && s.sys === a.sys);
    if (sy && Number.isFinite(a.x)) return { s: sy.i, x: Math.min(sy.w - 20, Math.max(20, a.x)), y: Number.isFinite(a.y) ? a.y : 30 };
    for (sy of D.systems.filter((s) => s.mvt === a.mvt)) {
      for (const [xa, , lab] of sy.segs) {
        if (!lab || !a.bar) continue; const [lo, hi] = X.segRange(lab);
        if (a.bar >= lo && a.bar <= hi) return { s: sy.i, x: xa + 30, y: 30 };
      }
    }
    return null;
  }
  function anchorFrom(svg, clientX, clientY) {
    const sy = D.systems[+svg.closest('.sys').id.slice(4)];
    const pt = svg.createSVGPoint(); pt.x = clientX; pt.y = clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    const x = Math.round(Math.max(0, Math.min(sy.w, p.x))), y = Math.round(p.y - Number(svg.dataset.top || 0));
    let note = null, nd = 90;
    for (const n of D.notes) if (n.s === sy.i && Math.abs(n.x - x) < nd) { nd = Math.abs(n.x - x); note = n.id; }
    return { mvt: sy.mvt, bar: barAt(sy, x), page: sy.page, sys: sy.sys, x, y, note };
  }
  function pins(sy, { topBand, H }) {
    const o = [];
    for (const memo of M.memos) {
      const at = memoPos(memo); if (!at || at.s !== sy.i) continue;
      const y = Math.max(66, Math.min(H - 4, topBand + at.y)), lab = memo.rehearsal ? memo.rehearsal.slice(0, 2) : '✎';
      o.push(`<g class="memo-pin k-${X.esc(memo.kind || 'note')}" data-memo="${X.esc(memo.id)}" tabindex="0" role="button" aria-label="${X.esc(memoLabel(memo))}のメモ：${X.esc(memo.text.slice(0, 40))}">`
        + `<title>${X.esc(memo.text)}</title><path d="M${at.x} ${y} l-14 -18 a30 30 0 1 1 28 0 z"/>`
        + `<text x="${at.x}" y="${y - 33}">${X.esc(lab)}</text></g>`);
    }
    return o.join('');
  }

  // ---------- API ----------
  async function api(path, opt = {}) {
    const res = await fetch(path, { credentials: 'same-origin', ...opt, headers: { Accept: 'application/json', ...(opt.body ? { 'Content-Type': 'application/json' } : {}) } });
    let body = null; try { body = await res.json(); } catch (e) { /* non-JSON */ }
    if (res.status === 401) { M.loggedIn = false; sync(); }
    if (!res.ok) throw new Error((body && body.error) || `保存できませんでした（${res.status}）`);
    return body;
  }
  const memoPath = (id) => `/api/memos/${encodeURIComponent(X.part)}${id ? '/' + encodeURIComponent(id) : ''}`;
  const loginUrl = () => `/login?return=${encodeURIComponent(location.pathname + location.search)}`;

  // ---------- UI ----------
  function sync() {
    $('memoPen').hidden = !M.enabled; $('memoListBtn').hidden = !M.enabled || !M.loggedIn;
    $('memoPen').setAttribute('aria-pressed', String(M.pen));
    $('memoPen').title = M.loggedIn ? 'ペンを押してから、メモを書きたい場所をタップ' : 'ログインするとメモを書けます';
    $('memoCount').textContent = M.memos.length ? ` ${M.memos.length}` : '';
    document.body.classList.toggle('memo-mode', M.pen);
  }
  function setPen(on) {
    M.pen = on && M.loggedIn; sync();
    if (M.pen) $('nowInfo').textContent = 'メモを書きたい場所をタップしてください（もう一度 ✎ か Esc で取り消し）。';
  }
  function openMemo(memo, anchor) {
    X.stop(); setPen(false);
    M.editing = memo || null; M.anchor = memo ? memo.anchor : anchor;
    const a = M.anchor;
    $('memoTitle').textContent = memo ? '練習メモを編集' : '練習メモを書く';
    $('memoWhere').textContent = `${memoLabel({ anchor: a })}${a.page ? ` · 原譜${a.page}ページ${a.sys}段目` : ''}`;
    $('memoReh').value = memo ? memo.rehearsal || '' : '';
    $('memoText').value = memo ? memo.text : '';
    document.querySelectorAll('[name=memoKind]').forEach((r) => { r.checked = r.value === ((memo && memo.kind) || 'note'); });
    $('memoMeta').textContent = memo ? `作成 ${fmtTime(memo.createdAt)}${memo.updatedAt !== memo.createdAt ? ` · 更新 ${fmtTime(memo.updatedAt)}` : ''}` : '保存すると日時も記録されます。';
    $('memoDelete').hidden = !memo; $('memoErr').hidden = true;
    if (!$('memo').open) $('memo').showModal();
    $('memoText').focus();
  }
  const showErr = (msg) => { $('memoErr').textContent = msg; $('memoErr').hidden = false; };
  async function save() {
    if (M.busy) return;
    const text = $('memoText').value.trim();
    if (!text) { showErr('メモを入力してください。'); return; }
    const kind = (document.querySelector('[name=memoKind]:checked') || {}).value || 'note';
    const body = JSON.stringify({ text, rehearsal: $('memoReh').value.trim(), kind, anchor: M.anchor });
    M.busy = true; $('memoSave').disabled = true;
    try {
      const saved = M.editing ? await api(memoPath(M.editing.id), { method: 'PUT', body }) : await api(memoPath(), { method: 'POST', body });
      M.memos = M.memos.filter((m) => m.id !== saved.id).concat(saved);
      $('memo').close(); X.rerender(); sync();
      $('nowInfo').textContent = `${memoLabel(saved)}にメモを保存しました（${fmtTime(saved.updatedAt)}）。`;
    } catch (e) { showErr(e.message); } finally { M.busy = false; $('memoSave').disabled = false; }
  }
  async function remove() {
    if (!M.editing || M.busy || !confirm('このメモを削除しますか？')) return;
    M.busy = true;
    try {
      await api(memoPath(M.editing.id), { method: 'DELETE' });
      M.memos = M.memos.filter((m) => m.id !== M.editing.id);
      $('memo').close(); X.rerender(); sync();
    } catch (e) { showErr(e.message); } finally { M.busy = false; }
  }
  function renderList() {
    const esc = X.esc;
    const sorted = [...M.memos].sort((a, b) => mvtOrder(a.anchor.mvt) - mvtOrder(b.anchor.mvt) || (a.anchor.bar || 0) - (b.anchor.bar || 0) || String(a.createdAt).localeCompare(b.createdAt));
    $('memoAccount').innerHTML = `${esc(M.email)} でログイン中 · <a href="/logout">ログアウト</a>`;
    $('memoItems').innerHTML = sorted.length ? sorted.map((m) => `<li class="k-${esc(m.kind || 'note')}"><div class="mi-h"><b>${esc(memoLabel(m))}</b><span class="mi-k">${KIND_LABEL[m.kind] || 'メモ'}</span>${memoPos(m) ? '' : '<span class="mi-k warn">位置不明</span>'}</div>`
      + `<p class="mi-t">${esc(m.text)}</p><div class="mi-f"><span>作成 ${esc(fmtTime(m.createdAt))}${m.updatedAt !== m.createdAt ? ` · 更新 ${esc(fmtTime(m.updatedAt))}` : ''}</span>`
      + `<span><button type="button" data-go="${esc(m.id)}">移動</button><button type="button" data-edit="${esc(m.id)}">編集</button></span></div></li>`).join('')
      : '<li class="empty">まだメモはありません。✎ を押して譜面の場所をタップしてください。</li>';
  }
  function goTo(id) {
    const memo = M.memos.find((m) => m.id === id); const at = memo && memoPos(memo); if (!at) return;
    X.setMvt(memo.anchor.mvt, false);
    const sec = $('sys-' + at.s); sec.scrollIntoView({ block: 'center', behavior: 'smooth' });
    const pin = sec.querySelector(`.memo-pin[data-memo="${CSS.escape(id)}"]`);
    if (pin) { pin.classList.add('flash'); setTimeout(() => pin.classList.remove('flash'), 1800); }
    const sc = sec.querySelector('.sc'), sy = D.systems[at.s];
    if (sc.scrollWidth > sc.clientWidth + 4) sc.scrollTo({ left: at.x / sy.w * sc.scrollWidth - sc.clientWidth / 2, behavior: 'smooth' });
  }
  const byPin = (el) => M.memos.find((x) => x.id === el.dataset.memo);

  function wire() {
    const score = $('score');
    const at = (e) => { const svg = e.target.closest('.sc svg'); return svg ? anchorFrom(svg, e.clientX, e.clientY) : null; };
    $('memoPen').onclick = () => {
      if (!M.loggedIn) { if (confirm('練習メモを書くにはログインが必要です。ログインページへ移動しますか？')) location.href = loginUrl(); return; }
      setPen(!M.pen);
    };
    $('memoListBtn').onclick = () => { renderList(); $('memoList').showModal(); };
    // Capture phase: memo pins and pen placement win over note playback in app.js.
    score.addEventListener('click', (e) => {
      const pin = e.target.closest('.memo-pin');
      if (pin) { e.stopImmediatePropagation(); const m = byPin(pin); if (m) openMemo(m); return; }
      if (!M.pen) return;
      const a = at(e); if (!a) return;
      e.stopImmediatePropagation(); e.preventDefault(); openMemo(null, a);
    }, true);
    // Shortcut: double-click / double-tap an empty spot (not a note) on the score.
    score.addEventListener('dblclick', (e) => {
      if (!M.loggedIn || e.target.closest('.note,.memo-pin')) return;
      const a = at(e); if (a) { e.preventDefault(); openMemo(null, a); }
    });
    let lastTap = null;
    score.addEventListener('touchend', (e) => {
      if (!M.loggedIn || M.pen || e.changedTouches.length !== 1 || e.target.closest('.note,.memo-pin')) { lastTap = null; return; }
      const t = e.changedTouches[0], now = Date.now();
      if (lastTap && now - lastTap.t < 350 && Math.hypot(t.clientX - lastTap.x, t.clientY - lastTap.y) < 30) {
        const svg = e.target.closest('.sc svg'); lastTap = null;
        if (svg) { e.preventDefault(); openMemo(null, anchorFrom(svg, t.clientX, t.clientY)); }
      } else lastTap = { t: now, x: t.clientX, y: t.clientY };
    });
    score.addEventListener('keydown', (e) => {
      const pin = e.target.closest('.memo-pin');
      if (pin && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); const m = byPin(pin); if (m) openMemo(m); }
    });
    $('memoForm').addEventListener('submit', (e) => { e.preventDefault(); save(); });
    $('memoCancel').onclick = () => $('memo').close();
    $('memoDelete').onclick = remove;
    $('memoItems').addEventListener('click', (e) => {
      const go = e.target.closest('[data-go]'), ed = e.target.closest('[data-edit]');
      if (go) { $('memoList').close(); goTo(go.dataset.go); }
      if (ed) { const m = M.memos.find((x) => x.id === ed.dataset.edit); $('memoList').close(); if (m) openMemo(m); }
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && M.pen) setPen(false); });
  }

  async function start() {
    R = window.__dynamic; X = R && R.ext; if (!X || X.print) return;
    D = R.data;
    let me = null;
    try { const res = await fetch('/api/me', { credentials: 'same-origin', headers: { Accept: 'application/json' } }); if (res.ok) me = await res.json(); } catch (e) { /* static preview or offline */ }
    if (!me || !me.enabled || !(me.memoParts || []).includes(X.part)) return;
    M.enabled = true; M.loggedIn = !!me.loggedIn; M.email = me.email || '';
    $('rehList').innerHTML = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').map((c) => `<option value="${c}">`).join('');
    X.addSvgHook(pins); wire();
    if (M.loggedIn) {
      try { M.memos = (await api(memoPath())).memos || []; X.rerender(); } catch (e) { $('nowInfo').textContent = `メモを読み込めませんでした：${e.message}`; }
    }
    sync();
  }
  if (window.__dynamic) start(); else document.addEventListener('dynamic:ready', start, { once: true });
})();
