/* DYNAMIC 譜読みアプリ — per-user, per-part, measure-linked practice memos.
 * Uses only __dynamic.ext; never changes score data, audit status or playback. */
import { resolveMemoAnchor, memoPosition } from './memo-model.mjs';

(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const KIND_LABEL = { note: 'メモ', issue: '課題', good: 'できた' };
  const QUICK_MARK_KIND = { '◎': 'good', '○': 'good', '△': 'issue', '×': 'issue' };
  const INTENT_KEY = 'dynamic-memo-intent';
  const M = { enabled: false, loggedIn: false, email: '', memos: [], editing: null, anchor: null, busy: false, pending: null };
  let R, X, D;
  const fmtTime = (iso) => { try { return new Date(iso).toLocaleString('ja-JP', { dateStyle: 'medium', timeStyle: 'short' }); } catch (e) { return iso; } };
  const mvtOrder = (k) => { const i = D.movements.findIndex((m) => m.key === k); return i < 0 ? 99 : i; };
  const canonical = (m) => resolveMemoAnchor(D, m.anchor);
  const memoPos = (m) => memoPosition(D, m.anchor);
  const kindOf = (m) => Object.hasOwn(KIND_LABEL, m.kind) ? m.kind : 'note';
  const sorted = (memos) => [...memos].sort((a, b) => mvtOrder(a.anchor?.mvt) - mvtOrder(b.anchor?.mvt)
    || (canonical(a)?.bar || 0) - (canonical(b)?.bar || 0) || String(a.createdAt).localeCompare(b.createdAt) || String(a.id).localeCompare(b.id));
  function memoLabel(memo) {
    const a = canonical(memo) || memo.anchor || {};
    return `${X.mvNum[a.mvt] || a.mvt || '不明'}楽章${a.bar ? ` ${a.bar}小節` : ''}`;
  }
  const atBar = (anchor) => M.memos.filter((m) => { const a = canonical(m); return a && a.mvt === anchor.mvt && a.bar === anchor.bar; });
  const latestMark = (anchor) => atBar(anchor).filter((m) => QUICK_MARK_KIND[m.text] === m.kind)
    .reduce((latest, m) => !latest || String(m.createdAt) >= String(latest.createdAt) ? m : latest, null);

  // Fixed rows BELOW the score/reading labels. Grid boundaries are original barlines;
  // repeated memos stack in their cell, and multi-rest memos retain exact bar labels.
  function memoBand(sy) {
    const groups = new Map();
    for (const memo of sorted(M.memos)) {
      const at = memoPos(memo); if (!at || at.s !== sy.i) continue;
      if (!groups.has(at.segment)) groups.set(at.segment, []);
      groups.get(at.segment).push(memo);
    }
    if (!groups.size) return '';
    const edges = [...new Set([0, sy.w, ...sy.segs.flatMap(([xa, xb]) => [xa, xb])])].sort((a, b) => a - b);
    const columns = edges.slice(1).map((x, i) => `${(x - edges[i]) / sy.w * 100}%`).join(' ');
    const cells = [...groups].map(([segment, memos]) => {
      const [xa, xb] = sy.segs[segment];
      const cards = memos.map((m) => `<button type="button" class="memo-card k-${kindOf(m)}" data-memo="${X.esc(m.id)}" aria-haspopup="dialog" aria-label="${X.esc(memoLabel(m))}のメモを編集：${X.esc(m.text.slice(0, 80))}">`
        + `<span class="memo-card-label">${canonical(m).bar}小節 · ${KIND_LABEL[kindOf(m)]}</span><span class="memo-card-text">${X.esc(m.text)}</span></button>`).join('');
      return `<div class="memo-cell" style="grid-column:${edges.indexOf(xa) + 1}/${edges.indexOf(xb) + 1};grid-row:1">${cards}</div>`;
    }).join('');
    return `<div class="memo-band" role="group" aria-label="この段の練習メモ" style="grid-template-columns:${columns}">${cells}</div>`;
  }

  // ---------- API ----------
  async function api(path, opt = {}) {
    const res = await fetch(path, { credentials: 'same-origin', ...opt, headers: { Accept: 'application/json', ...(opt.body ? { 'Content-Type': 'application/json' } : {}) } });
    let body = null; try { body = await res.json(); } catch (e) { /* non-JSON */ }
    if (res.status === 401) { M.loggedIn = false; M.email = ''; M.memos = []; X.rerender(); sync(); }
    if (!res.ok) throw new Error((body && body.error) || `保存できませんでした（${res.status}）`);
    return body;
  }
  const memoPath = (id) => `/api/memos/${encodeURIComponent(X.part)}${id ? '/' + encodeURIComponent(id) : ''}`;
  const loginUrl = () => `/login?return=${encodeURIComponent(location.pathname + location.search)}`;
  function sync() {
    $('memoSettings').hidden = !M.enabled;
    $('memoListBtn').hidden = !M.loggedIn;
    $('memoStatus').textContent = M.loggedIn ? `ログイン中：${M.email}` : 'メモ：未ログイン（小節のメニューからログイン）';
    $('memoStatus').classList.toggle('is-logged-in', M.loggedIn);
    $('memoCount').textContent = M.memos.length ? ` ${M.memos.length}` : '';
  }
  function askLogin(anchor) {
    M.pending = anchor || null;
    if (!$('memoLoginPrompt').open) $('memoLoginPrompt').showModal();
  }
  function openMemo(memo, anchor) {
    if (M.busy) return;
    if (!M.loggedIn) { askLogin(memo ? canonical(memo) : anchor); return; }
    X.stop();
    M.editing = memo || null;
    // Legacy unresolved notes stay editable in the list without inventing a bar.
    M.anchor = memo ? canonical(memo) || memo.anchor : anchor;
    $('memoTitle').textContent = memo ? '練習メモを編集' : `この${M.anchor.bar}小節目にメモを追加`;
    $('memoWhere').textContent = memoLabel({ anchor: M.anchor }) + (memo && !memoPos(memo) ? ' · 位置不明（元の記録を保持）' : ' · 小節の下に表示');
    $('memoText').value = memo ? memo.text : '';
    document.querySelectorAll('[name=memoKind]').forEach((r) => { r.checked = r.value === (memo ? kindOf(memo) : 'note'); });
    $('memoMeta').textContent = memo ? `作成 ${fmtTime(memo.createdAt)}${memo.updatedAt !== memo.createdAt ? ` · 更新 ${fmtTime(memo.updatedAt)}` : ''}` : '保存すると日時も記録されます。';
    $('memoDelete').hidden = !memo; $('memoErr').hidden = true;
    if (!$('memo').open) $('memo').showModal();
    $('memoText').focus();
  }
  const showErr = (msg) => { $('memoErr').textContent = msg; $('memoErr').hidden = false; };
  function busy(on) {
    M.busy = on;
    $('memoForm').querySelectorAll('input,textarea,button').forEach((el) => { el.disabled = on; });
  }
  async function save() {
    if (M.busy) return;
    const text = $('memoText').value.trim();
    if (!text) { showErr('メモを入力してください。'); return; }
    const kind = document.querySelector('[name=memoKind]:checked')?.value || 'note';
    const editing = M.editing;
    const fields = { text, kind, anchor: M.anchor };
    // No rehearsal input or new rehearsal field; retain old metadata on an edit.
    if (editing?.rehearsal) fields.rehearsal = editing.rehearsal;
    const body = JSON.stringify(fields);
    busy(true);
    try {
      const saved = await api(memoPath(editing?.id), { method: editing ? 'PUT' : 'POST', body });
      M.memos = M.memos.filter((m) => m.id !== saved.id).concat(saved);
      $('memo').close(); X.rerender(); sync();
      $('nowInfo').textContent = `${memoLabel(saved)}にメモを保存しました（${fmtTime(saved.updatedAt)}）。`;
    } catch (e) { showErr(e.message); } finally { busy(false); }
  }
  async function saveMark(anchor, mark) {
    if (M.busy || !M.loggedIn || !QUICK_MARK_KIND[mark]) return;
    M.busy = true;
    try {
      const saved = await api(memoPath(), { method: 'POST', body: JSON.stringify({ text: mark, kind: QUICK_MARK_KIND[mark], anchor }) });
      M.memos.push(saved);
      X.rerender(); sync();
      $('nowInfo').textContent = `${memoLabel(saved)}に${mark}を記録しました（${fmtTime(saved.createdAt)}）。`;
    } catch (e) { $('nowInfo').textContent = `${mark}を記録できませんでした：${e.message}`; }
    finally {
      M.busy = false;
      // The menu can be reopened while the request is in flight.
      document.querySelectorAll('#ctx .ctx-quick button').forEach((button) => { button.disabled = false; });
    }
  }
  async function remove() {
    if (!M.editing || M.busy || !confirm('このメモを削除しますか？')) return;
    const id = M.editing.id;
    busy(true);
    try {
      await api(memoPath(id), { method: 'DELETE' });
      M.memos = M.memos.filter((m) => m.id !== id);
      $('memo').close(); X.rerender(); sync();
    } catch (e) { showErr(e.message); } finally { busy(false); }
  }
  function showList(anchor = null) {
    const esc = X.esc, items = sorted(anchor ? atBar(anchor) : M.memos);
    $('memoListTitle').textContent = anchor ? `${memoLabel({ anchor })}のメモ` : '練習メモ一覧';
    $('memoAccount').innerHTML = `${esc(M.email)} でログイン中 · <a href="/logout">ログアウト</a>`;
    $('memoItems').innerHTML = items.length ? items.map((m) => `<li class="k-${kindOf(m)}"><div class="mi-h"><b>${esc(memoLabel(m))}</b><span class="mi-k">${KIND_LABEL[kindOf(m)]}</span>${memoPos(m) ? '' : '<span class="mi-k warn">位置不明</span>'}</div>`
      + `<p class="mi-t">${esc(m.text)}</p><div class="mi-f"><span>作成 ${esc(fmtTime(m.createdAt))}${m.updatedAt !== m.createdAt ? ` · 更新 ${esc(fmtTime(m.updatedAt))}` : ''}</span>`
      + `<span><button type="button" data-go="${esc(m.id)}"${memoPos(m) ? '' : ' disabled'}>移動</button><button type="button" data-edit="${esc(m.id)}">編集</button></span></div></li>`).join('')
      : '<li class="empty">まだメモはありません。小節をクリックして「この小節にメモを追加」を選んでください。</li>';
    if (!$('memoList').open) $('memoList').showModal();
  }
  function goTo(id) {
    const memo = M.memos.find((m) => m.id === id), at = memo && memoPos(memo); if (!at) return;
    X.setMvt(at.anchor.mvt, false);
    const sec = $('sys-' + at.s); sec.scrollIntoView({ block: 'center', behavior: 'smooth' });
    const card = sec.querySelector(`.memo-card[data-memo="${CSS.escape(id)}"]`);
    if (card) { card.classList.add('flash'); card.focus({ preventScroll: true }); setTimeout(() => card.classList.remove('flash'), 1800); }
    const sc = sec.querySelector('.sc'), sy = D.systems.find((s) => s.i === at.s);
    if (sc.scrollWidth > sc.clientWidth + 4) sc.scrollTo({ left: at.x / sy.w * sc.scrollWidth - sc.clientWidth / 2, behavior: 'smooth' });
  }
  function menuActions(hit) {
    const anchor = { mvt: hit.mvt, bar: hit.bar };
    if (!memoPosition(D, anchor)) return [];
    const actions = [{ label: `この${hit.bar}小節目にメモを追加`, run: () => openMemo(null, anchor) }];
    if (M.loggedIn) {
      const current = latestMark(anchor)?.text;
      actions.unshift({ position: 'top', label: `${hit.bar}小節目の練習印`, group: Object.keys(QUICK_MARK_KIND).map((mark) => ({
        label: mark, title: `${hit.bar}小節目に${mark}を記録`, pressed: current === mark, disabled: M.busy,
        run: () => saveMark(anchor, mark),
      })) });
      const count = atBar(anchor).length;
      if (count) actions.push({ label: `この小節のメモを見る（${count}件）`, run: () => showList(anchor) });
      actions.push({ label: '練習メモ一覧', run: () => showList() });
    }
    return actions;
  }
  function wire() {
    $('memoLoginGo').onclick = () => {
      try { if (M.pending) sessionStorage.setItem(INTENT_KEY, JSON.stringify({ part: X.part, anchor: M.pending })); } catch (e) { /* optional */ }
      $('memoLoginPrompt').close(); location.assign(loginUrl());
    };
    $('memoListBtn').onclick = () => showList();
    // Only existing memo cards intercept clicks. There is no pen/free-placement mode.
    $('score').addEventListener('click', (e) => {
      const card = e.target.closest('.memo-card'); if (!card) return;
      e.stopImmediatePropagation();
      const memo = M.memos.find((m) => m.id === card.dataset.memo); if (memo) openMemo(memo);
    }, true);
    $('memoForm').addEventListener('submit', (e) => { e.preventDefault(); save(); });
    $('memo').addEventListener('cancel', (e) => { if (M.busy) e.preventDefault(); });
    $('memoCancel').onclick = () => { if (!M.busy) $('memo').close(); };
    $('memoDelete').onclick = remove;
    $('memoItems').addEventListener('click', (e) => {
      const go = e.target.closest('[data-go]'), ed = e.target.closest('[data-edit]');
      if (go) { $('memoList').close(); goTo(go.dataset.go); }
      if (ed) { const m = M.memos.find((x) => x.id === ed.dataset.edit); $('memoList').close(); if (m) openMemo(m); }
    });
  }
  async function start() {
    R = window.__dynamic; X = R?.ext;
    if (!X || X.print || !X.addBarMenuHook || !X.addSystemHook) return;
    D = R.data;
    let me = null;
    try { const res = await fetch('/api/me', { credentials: 'same-origin', headers: { Accept: 'application/json' } }); if (res.ok) me = await res.json(); } catch (e) { /* static preview or offline */ }
    if (!me?.enabled || !(me.memoParts || []).includes(X.part)) return;
    M.enabled = true; M.loggedIn = !!me.loggedIn; M.email = me.email || '';
    wire();
    if (M.loggedIn) {
      try { M.memos = (await api(memoPath())).memos || []; } catch (e) { $('nowInfo').textContent = `メモを読み込めませんでした：${e.message}`; }
    }
    X.addSystemHook(memoBand); X.addBarMenuHook(menuActions); X.rerender(); sync();
    if (M.loggedIn) {
      try {
        const pending = JSON.parse(sessionStorage.getItem(INTENT_KEY) || 'null');
        if (pending?.part === X.part) {
          sessionStorage.removeItem(INTENT_KEY);
          const at = memoPosition(D, pending.anchor);
          if (at) { X.setMvt(at.anchor.mvt, false); R.jumpTo(at.anchor.bar); openMemo(null, at.anchor); }
        }
      } catch (e) { /* optional navigation hint */ }
    }
  }
  if (window.__dynamic) start(); else document.addEventListener('dynamic:ready', start, { once: true });
})();
