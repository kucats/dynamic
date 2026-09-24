/* DYNAMIC 譜読みアプリ — reader */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const PART = params.get('part') || 'dvorak8-horn2';
  const PRINT = params.has('print');
  const LEGACY_SIZES = { s: 36, m: 44, l: 56 };
  const ROWSETS = {
    horn: [['w', 'lw', 1.0, '記譜ドレミ', 'cw', true], ['f', 'lf', 0.78, 'F管の読み替え', 'cf', false], ['s', 'ls', 0.64, '実音', 'cs', false]],
    trombone: [['w', 'lw', 1.0, '音名', 'cw', true], ['p', 'lp', 0.8, 'ポジション', 'cp', true]],
  };
  let ROWS = ROWSETS.horn;
  const val = (n, k) => (k === 'w' ? n.w : k === 'f' ? n.f : k === 's' ? n.snd : [String(n.pos ?? '–'), '', 0]);
  const MV_NUM = { I: 1, II: 2, III: 3, IV: 4 };

  // ---------- settings (per viewer, optional) ----------
  const DEF = { rows: { w: true, f: false, s: false }, fontSize: 44, barPosition: 'bottom', sound: 's', tempo: 100, squeeze: true,
    fromSel: true, follow: true, metro: false, lines: true, zoom: innerWidth < 760 ? 2.6 : 1 };
  let S = structuredClone(DEF);
  try {
    const stored = JSON.parse(localStorage.getItem('dynamic-settings') || '{}');
    Object.assign(S, stored);
    const legacySize = LEGACY_SIZES[stored.size] || DEF.fontSize;
    S.fontSize = Math.max(26, Math.min(72, stored.fontSize == null || !Number.isFinite(Number(stored.fontSize)) ? legacySize : Number(stored.fontSize)));
    if (!['bottom', 'top', 'off'].includes(S.barPosition)) S.barPosition = stored.bars === false ? 'off' : 'bottom';
  } catch (e) { /* ignore */ }
  if (PRINT) {
    S.zoom = 1;
    S.fontSize = LEGACY_SIZES[params.get('size')] || Math.max(26, Math.min(72, Number(params.get('size')) || 44));
    S.barPosition = 'bottom';
  }
  const save = () => {
    if (PRINT) return;
    if (D) {
      S.rowsByPart = S.rowsByPart || {}; S.rowsByPart[PART] = S.rows;
      S.soundByPart = S.soundByPart || {}; S.soundByPart[PART] = S.sound;
    }
    try { localStorage.setItem('dynamic-settings', JSON.stringify(S)); } catch (e) { /* ignore */ }
  };

  const svgHooks = [];                // extensions (memo.js) draw extra SVG per system
  let D = null, byId = new Map(), cur = null, playing = null, ctx = null, master = null, practiceOsc = [], practiceTimer = null, fontRenderFrame = 0;

  // ---------- label layout ----------
  function rowWidth(lbl) {           // label width in em (compact metrics)
    const [sol, oct] = lbl; const base = sol.replace(/[♭♯𝄫𝄪]/g, ''); const acc = sol.length - base.length;
    const bw = base === 'ファ' ? 1.62 : /^[A-H]$/.test(base) ? 0.74 : /^[0-9–?]+$/.test(base) ? 0.62 : 1.0;
    return bw + 0.45 * acc + (oct === '' ? 0.1 : 0.42);
  }
  function labelWidth(n, fs) {
    let w = 0;
    for (const [k, , sc] of ROWS) if (S.rows[k]) w = Math.max(w, rowWidth(val(n, k)) * sc);
    return w * fs + 8;
  }
  function labelHeight(fs) {
    let h = 0; for (const [k, , sc] of ROWS) if (S.rows[k]) h += fs * sc * 1.08; return Math.max(h, fs * 0.6);
  }
  function place(xs, ws, gap = 6) {   // 1-D non-overlapping placement, least-squares displacement (PAV)
    const n = xs.length, s = new Array(n).fill(0);
    for (let i = 1; i < n; i++) s[i] = s[i - 1] + (ws[i - 1] + ws[i]) / 2 + gap;
    const blocks = [];
    for (let i = 0; i < n; i++) {
      blocks.push([xs[i] - s[i], 1]);
      while (blocks.length > 1 && blocks[blocks.length - 2][0] / blocks[blocks.length - 2][1] > blocks[blocks.length - 1][0] / blocks[blocks.length - 1][1]) {
        const b = blocks.pop(); blocks[blocks.length - 1][0] += b[0]; blocks[blocks.length - 1][1] += b[1];
      }
    }
    const out = []; let i = 0;
    for (const [sm, c] of blocks) for (let k = 0; k < c; k++, i++) out.push(sm / c + s[i]);
    return out;
  }
  const LOW = 0.84;                   // lower lane is drawn slightly smaller
  function layout(xs, ws, ps, maxd = 70) {
    // One lane when labels fit near their notes. Otherwise crowded runs are split by pitch:
    // higher notes go to the upper lane, lower notes to the lower (smaller) lane.
    const n = xs.length; if (!n) return [[], [], ws];
    let c = place(xs, ws);
    if (Math.max(...c.map((v, i) => Math.abs(v - xs[i]))) <= maxd) return [c, new Array(n).fill(0), ws];
    const lane = new Array(n).fill(0);
    const crowded = (i) => xs[i] - xs[i - 1] < (ws[i] + ws[i - 1]) / 2 + 6;
    let i = 0;
    while (i < n) {
      let j = i; while (j + 1 < n && crowded(j + 1)) j++;
      if (j > i) {
        const run = []; for (let k = i; k <= j; k++) run.push(k);
        const hi = Math.max(...run.map((k) => ps[k])), lo = Math.min(...run.map((k) => ps[k]));
        if (hi === lo) run.forEach((k, t) => { lane[k] = t % 2; });
        else {
          const thr = (hi + lo) / 2;
          run.forEach((k) => { lane[k] = ps[k] > thr ? 0 : 1; });
          // repeated equal pitches next to each other inside one lane still alternate when very close
          for (let t = 1; t < run.length; t++) {
            const a = run[t - 1], b = run[t];
            if (lane[a] === lane[b] && ps[a] === ps[b] && xs[b] - xs[a] < (ws[a] + ws[b]) / 4) lane[b] = 1 - lane[a];
          }
        }
      }
      i = j + 1;
    }
    const w2 = ws.map((w, k) => (lane[k] ? w * LOW : w));
    c = new Array(n);
    for (const r of [0, 1]) {
      const idx = []; for (let k = 0; k < n; k++) if (lane[k] === r) idx.push(k);
      const cc = place(idx.map((k) => xs[k]), idx.map((k) => w2[k]));
      idx.forEach((k, t) => { c[k] = cc[t]; });
    }
    return [c, lane, w2];
  }
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  function textRow(cls, lbl, x, y, fs) {
    const [sol, oct] = lbl; const base = sol.replace(/[♭♯𝄫𝄪]/g, ''); const acc = sol.slice(base.length);
    const ls = base === 'ファ' ? ' letter-spacing="-0.2em"' : '';
    let t = `<tspan${ls}>${base}</tspan>`;
    if (acc) t += `<tspan font-size="${Math.round(fs * 0.72)}" dx="${Math.round(fs * (ls ? 0.2 : 0.04))}">${acc}</tspan>`;
    else if (ls) t += `<tspan dx="${Math.round(fs * 0.2)}"></tspan>`;
    if (oct !== '') t += `<tspan font-size="${Math.round(fs * 0.5)}" dy="${-Math.round(fs * 0.42)}">${oct}</tspan>`;
    return `<text class="${cls}" x="${x.toFixed(1)}" y="${y.toFixed(1)}" font-size="${Math.round(fs)}">${t}</text>`;
  }

  // ---------- rendering ----------
  function systemSVG(sy) {
    const fs = Math.max(26, Math.min(72, Number(S.fontSize) || 44)), W = sy.w, h = sy.h;
    const ns = D.notes.filter((n) => n.s === sy.i).sort((a, b) => a.x - b.x);
    const ws0 = ns.map((n) => labelWidth(n, fs));
    const [cx, lane, ws] = layout(ns.map((n) => n.x), ws0, ns.map((n) => n.w[2]));
    const lh = labelHeight(fs), strip = 40, topBand = S.barPosition === 'top' ? strip : 0, laneH = lh + 12;
    const lanes = ns.length ? Math.max(...lane) + 1 : 0;
    const H = topBand + h + strip + (ns.length ? lanes * laneH + 10 : 4);
    const o = [`<svg viewBox="0 0 ${W} ${H}" data-top="${topBand}" role="group" aria-label="原譜${sy.page}ページ ${sy.sys}段目"><image href="${sy.img}" x="0" y="${topBand}" width="${W}" height="${h}"/>`];
    if (S.barPosition !== 'off') for (const [xa, xb, lab] of sy.segs) {
      if (S.barPosition === 'top') {
        o.push(`<line class="bt" x1="${xa}" y1="4" x2="${xa}" y2="34"/>`);
        if (lab) o.push(`<text class="bn" x="${xa + 8}" y="29">${esc(lab)}</text>`);
      } else {
        o.push(`<line class="bt" x1="${xa}" y1="${topBand + h - 8}" x2="${xa}" y2="${topBand + h + 30}"/>`);
        if (lab) o.push(`<text class="bn" x="${xa + 8}" y="${topBand + h + 28}">${esc(lab)}</text>`);
      }
    }
    const tops = ns.map((n, i) => topBand + h + strip + lane[i] * laneH);
    ns.forEach((n, i) => {
      o.push(`<polyline class="leader${n.tie ? ' tie' : ''}" points="${n.x},${(topBand + n.y + 20).toFixed(0)} ${n.x},${topBand + h + 2} ${cx[i].toFixed(1)},${tops[i].toFixed(1)}"/>`);
    });
    ns.forEach((n, i) => {
      const w = ws[i], top = tops[i], ny = topBand + n.y;
      const fsl = lane[i] ? fs * LOW : fs, lhl = lane[i] ? lh * LOW : lh;
      let y = top, rows = '';
      for (const [k, cls, sc] of ROWS) {
        if (!S.rows[k]) continue;
        const f = fsl * sc; y += f * 0.95;
        rows += textRow(cls, val(n, k), cx[i], y, f);
        if (k === 'w' && n.old) rows += `<text class="lw" x="${(cx[i] + w / 2 - fsl * 0.18).toFixed(1)}" y="${(y - fsl * 0.5).toFixed(1)}" font-size="${Math.round(fsl * 0.4)}" fill="#c0392b">※</text>`;
        y += f * 0.13;
      }
      const cls = 'note' + (n.tie ? ' tiec' : '') + (n.unc ? ' unc' : '');
      o.push(`<g class="${cls}" data-id="${n.id}" tabindex="0" role="button" aria-label="${n.bar}小節 ${esc(n.w[0])}${n.w[1]}。クリックで実音、ダブルクリックまたは右クリックでロングトーン練習">`
        + `<rect class="hit" x="${n.x - 34}" y="${ny - 34}" width="68" height="68"/>`
        + `<ellipse class="halo" cx="${n.x}" cy="${ny}" rx="30" ry="25"/>`
        + `<rect class="lbg" x="${(cx[i] - w / 2).toFixed(1)}" y="${(top + 2).toFixed(1)}" width="${w.toFixed(1)}" height="${(lhl + 4).toFixed(1)}" rx="8"/>`
        + rows + `<rect class="hit" x="${(cx[i] - w / 2).toFixed(1)}" y="${top.toFixed(1)}" width="${w.toFixed(1)}" height="${(lhl + 8).toFixed(1)}"/></g>`);
    });
    for (const hook of svgHooks) o.push(hook(sy, { topBand, H }));
    o.push('</svg>');
    return o.join('');
  }

  function renderScore() {
    const main = $('score'); const html = [];
    if (PRINT) html.push(`<div class="printhead"><h1>${esc(D.title)}</h1><div>${esc(D.subtitle)} ／ 茶色の数字＝小節番号 ／ 線で音符とつながっています ／ 薄い字＝タイの続き ／ キューには付けていません</div></div>`);
    for (const m of D.movements) {
      html.push(`<h2 class="mv" id="mv-${m.key}">${esc(m.title)} <small>${m.notes}音</small></h2>`);
      for (const sy of D.systems.filter((s) => s.mvt === m.key)) {
        const labs = sy.segs.map((g) => g[2]).filter(Boolean);
        const rng = labs.length ? `${labs[0].split('–')[0]}〜${labs[labs.length - 1].split('–').pop()}小節` : '';
        html.push(`<section class="sys" id="sys-${sy.i}" data-mvt="${sy.mvt}"><div class="cap">原譜 ${sy.page}ページ ${sy.sys}段目 · ${rng}</div><div class="sc">${systemSVG(sy)}</div></section>`);
      }
    }
    main.innerHTML = html.join('');
    document.body.classList.toggle('nolines', !S.lines);
    document.documentElement.style.setProperty('--zoom', S.zoom);
    if (cur) mark(cur, false);
  }

  // ---------- selection ----------
  function mark(id, scroll) {
    document.querySelectorAll('.note.on').forEach((e) => e.classList.remove('on'));
    document.querySelectorAll('.sys.cur').forEach((e) => e.classList.remove('cur'));
    const el = document.querySelector(`.note[data-id="${id}"]`); if (!el) return;
    el.classList.add('on'); const sec = el.closest('.sys'); sec.classList.add('cur');
    if (scroll) {
      const r = sec.getBoundingClientRect(), top = $('bar').getBoundingClientRect().bottom;
      if (r.top < top + 4 || r.bottom > innerHeight - 10) sec.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
    const sc = el.closest('.sc'), n = byId.get(id), sy = D.systems[n.s];
    if (sc.scrollWidth > sc.clientWidth + 4) {
      const fx = n.x / sy.w * sc.scrollWidth - sc.clientWidth / 2;
      if (Math.abs(sc.scrollLeft - fx) > sc.clientWidth * 0.3) sc.scrollTo({ left: fx, behavior: 'smooth' });
    }
  }
  function select(id, { sound = false, scroll = true } = {}) {
    const n = byId.get(id); if (!n) return;
    cur = id; mark(id, scroll);
    $('nowW').innerHTML = `${esc(n.w[0])}<sup>${n.w[1]}</sup>${n.old ? '<small>※</small>' : ''}`;
    if (D.instrument === 'trombone') {
      $('nowF').innerHTML = `ポジション ${n.pos ?? '–'}`; $('nowS').innerHTML = '';
    } else {
      $('nowF').innerHTML = S.rows.f || D.showF ? `F管 ${esc(n.f[0])}<sup>${n.f[1]}</sup>` : '';
      $('nowS').innerHTML = `実音 ${esc(n.snd[0])}<sup>${n.snd[1]}</sup>`;
    }
    $('nowInfo').textContent = `${MV_NUM[n.mvt] || n.mvt}楽章 ${n.bar}小節${D.instrument === "trombone" ? "" : " · in " + n.key}${n.tie ? ' · タイの続き' : ''}${n.old ? ' · ヘ音記号は旧記譜' : ''}${n.unc ? ' · 要確認：' + n.unc : ''} · ${id}/${D.notes.length}`;
    setMvt(n.mvt, false);
    if (sound && !playing) one(n);
  }

  // ---------- audio ----------
  async function audio() {
    if (!ctx) {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      master = ctx.createGain(); master.gain.value = 0.9;
      const comp = ctx.createDynamicsCompressor(); master.connect(comp); comp.connect(ctx.destination);
    }
    await ctx.resume();
  }
  const pitchOf = (n) => (S.sound === 'w' ? n.w[2] : S.sound === 'f' ? n.f[2] : n.snd[2]);
  function voice(m, t0, d) {
    const f = 440 * 2 ** ((m - 69) / 12);
    const o1 = ctx.createOscillator(), o2 = ctx.createOscillator(), lp = ctx.createBiquadFilter(), g = ctx.createGain(), g2 = ctx.createGain();
    o1.type = 'sawtooth'; o1.frequency.value = f; o2.type = 'sine'; o2.frequency.value = f;
    lp.type = 'lowpass'; lp.frequency.value = Math.min(3800, f * 3.2); lp.Q.value = 0.5; g2.gain.value = 0.6;
    o1.connect(lp); lp.connect(g); o2.connect(g2); g2.connect(g); g.connect(master);
    const a = 0.035, r = Math.min(0.08, d * 0.3), pk = 0.16;
    g.gain.setValueAtTime(0, t0); g.gain.linearRampToValueAtTime(pk, t0 + a);
    g.gain.setValueAtTime(pk * 0.85, Math.max(t0 + a, t0 + d - r)); g.gain.linearRampToValueAtTime(0, t0 + d);
    o1.start(t0); o2.start(t0); o1.stop(t0 + d + 0.03); o2.stop(t0 + d + 0.03);
    return [o1, o2];
  }
  function click(t0, accent) {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.value = accent ? 1600 : 1100; g.gain.setValueAtTime(0.12, t0); g.gain.exponentialRampToValueAtTime(0.001, t0 + 0.05);
    o.connect(g); g.connect(master); o.start(t0); o.stop(t0 + 0.06); return [o];
  }
  async function one(n, actualSound = true) { await audio(); voice(actualSound ? n.snd[2] : pitchOf(n), ctx.currentTime + 0.02, 0.85); }

  function stopPractice() {
    clearTimeout(practiceTimer); practiceTimer = null;
    practiceOsc.forEach((o) => { try { o.stop(); } catch (e) { /* already stopped */ } });
    practiceOsc = [];
    const button = $('practicePlay');
    if (button) { button.textContent = '▶ ロングトーン'; button.classList.remove('on'); }
  }
  async function startPractice(n) {
    stopPractice(); await audio();
    if (!$('practice').open || Number($('practice').dataset.noteId) !== n.id) return;
    const seconds = Number($('practiceDuration').value) || 4;
    practiceOsc = voice(n.snd[2], ctx.currentTime + 0.02, seconds);
    $('practicePlay').textContent = '■ 停止'; $('practicePlay').classList.add('on');
    practiceTimer = setTimeout(stopPractice, seconds * 1000 + 120);
  }
  function openPractice(id) {
    const n = byId.get(id); if (!n) return;
    stop(); stopPractice(); select(id, { sound: false, scroll: false });
    const pitch = (p) => `${p[0]}${p[1]}`;
    $('practiceWritten').textContent = `譜面：${pitch(n.w)} · ${MV_NUM[n.mvt] || n.mvt}楽章 ${n.bar}小節`;
    $('practiceSounding').textContent = `吹く音（実音）：${pitch(n.snd)}`;
    $('practice').dataset.noteId = n.id;
    if (!$('practice').open) $('practice').showModal();
  }

  let mvtNotes = new Map();
  function timeline(mv) {
    const m = D.movements.find((x) => x.key === mv); const tf = S.tempo / 100;
    const ev = []; let t = 0, prevEmpty = false;
    for (const [bar, len, spw, ds] of m.timeline) {
      const ids = mvtNotes.get(mv + ':' + bar) || [];
      const empty = !ids.length;
      if (empty && S.squeeze && prevEmpty) continue;
      prevEmpty = empty; const s = spw / tf;
      ev.push({ m: 1, bar, ds, t });
      for (const id of ids) { const n = byId.get(id); ev.push({ id, t: t + n.off * s, d: n.dur * s, ds }); }
      t += len * s;
    }
    return { ev, total: t };
  }
  async function play() {
    stop(); await audio();
    const mv = currentMvt; const { ev, total } = timeline(mv);
    let st = 0;
    if (S.fromSel && cur && byId.get(cur).mvt === mv) { const e = ev.find((x) => x.id === cur); if (e) st = e.t; }
    const t0 = ctx.currentTime + 0.15 - st, osc = [], timers = [];
    const ne = ev.filter((e) => !e.m && e.t >= st - 1e-6);
    for (let i = 0; i < ne.length; i++) {
      const e = ne[i], n = byId.get(e.id);
      if (n.tie && i > 0 && byId.get(ne[i - 1].id).mvt === n.mvt) continue;
      if (!e.d) continue;
      let d = e.d, j = i;
      while (j + 1 < ne.length && byId.get(ne[j + 1].id).tie) { j++; d = ne[j].t + ne[j].d - e.t; }
      osc.push(...voice(pitchOf(n), t0 + e.t, Math.max(0.05, d * 0.93)));
    }
    for (const e of ev) {
      if (e.t < st - 1e-6) continue;
      if (e.m && S.metro) osc.push(...click(t0 + e.t, true));
      const ms = (t0 + e.t - ctx.currentTime) * 1000;
      timers.push(setTimeout(() => {
        if (e.m) $('barNow').textContent = `${MV_NUM[mv] || mv}楽章 ${e.bar}小節${e.ds ? '（D.S.後）' : ''}`;
        else select(e.id, { scroll: S.follow });
      }, Math.max(0, ms)));
    }
    timers.push(setTimeout(stop, (t0 + total - ctx.currentTime) * 1000 + 300));
    playing = { osc, timers }; $('play').textContent = '■ 停止'; $('play').classList.add('on');
  }
  function stop() {
    if (!playing) return;
    playing.timers.forEach(clearTimeout); playing.osc.forEach((o) => { try { o.stop(); } catch (e) { /* ignore */ } });
    playing = null; $('play').textContent = '▶ 再生'; $('play').classList.remove('on'); $('barNow').textContent = '';
  }

  // ---------- movements / jump ----------
  let currentMvt = null;
  function setMvt(key, scroll) {
    currentMvt = key;
    document.querySelectorAll('#mvts button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.k === key)));
    if (scroll) { stop(); $('mv-' + key).scrollIntoView({ behavior: 'smooth' }); }
  }
  function segRange(lab) { const [a, b] = lab.split('–').map(Number); return [a, b || a]; }
  function jumpTo(bar) {
    const mv = currentMvt;
    for (const sy of D.systems.filter((s) => s.mvt === mv)) {
      for (const [xa, xb, lab] of sy.segs) {
        if (!lab) continue; const [a, b] = segRange(lab);
        if (bar >= a && bar <= b) {
          const first = D.notes.find((n) => n.mvt === mv && n.bar >= bar);
          if (first && first.bar <= b) select(first.id, { scroll: true });
          else { cur = null; $('sys-' + sy.i).scrollIntoView({ block: 'center', behavior: 'smooth' }); }
          flash(sy, xa, xb);
          if (first && first.bar > b) cur = first.id;   // playback starts from the next played note
          return;
        }
      }
    }
    $('nowInfo').textContent = `${bar}小節は見つかりませんでした。`;
  }
  function flash(sy, xa, xb) {
    const svg = $('sys-' + sy.i).querySelector('svg');
    const r = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    r.setAttribute('class', 'segflash'); r.setAttribute('x', xa); r.setAttribute('y', S.barPosition === 'top' ? 40 : 0);
    r.setAttribute('width', xb - xa); r.setAttribute('height', sy.h);
    svg.insertBefore(r, svg.children[1]); setTimeout(() => r.remove(), 1800);
  }

  // ---------- wiring ----------
  function syncControls() {
    document.querySelectorAll('[data-row]').forEach((c) => { c.checked = !!S.rows[c.dataset.row]; });
    $('fontSize').value = S.fontSize; $('fontSizeV').textContent = `${S.fontSize}px`;
    document.querySelectorAll('[data-bar-pos]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.barPos === S.barPosition)));
    $('sound').value = S.sound; $('tempo').value = S.tempo; $('tempoV').textContent = S.tempo + '%';
    for (const k of ['squeeze', 'fromSel', 'follow', 'metro', 'lines']) $(k).checked = !!S[k];
  }
  function wire() {
    $('score').addEventListener('click', (e) => {
      const g = e.target.closest('.note'); if (!g) return;
      if (e.detail >= 2) { e.preventDefault(); openPractice(+g.dataset.id); return; }
      select(+g.dataset.id, { sound: true, scroll: false });
    });
    $('score').addEventListener('dblclick', (e) => {
      const g = e.target.closest('.note'); if (g) { e.preventDefault(); openPractice(+g.dataset.id); }
    });
    $('score').addEventListener('contextmenu', (e) => {
      const g = e.target.closest('.note'); if (g) { e.preventDefault(); openPractice(+g.dataset.id); }
    });
    $('score').addEventListener('keydown', (e) => {
      const g = e.target.closest('.note'); if (g && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); select(+g.dataset.id, { sound: true, scroll: false }); }
    });
    $('play').onclick = () => (playing ? stop() : play());
    $('one').onclick = () => { if (cur) one(byId.get(cur)); else select(D.notes[0].id, { sound: true }); };
    $('prev').onclick = () => select(Math.max(1, (cur || 2) - 1), { sound: true });
    $('next').onclick = () => select(Math.min(D.notes.length, (cur || 0) + 1), { sound: true });
    $('tempo').oninput = () => { S.tempo = +$('tempo').value; $('tempoV').textContent = S.tempo + '%'; save(); };
    $('fontSize').oninput = () => {
      S.fontSize = +$('fontSize').value; $('fontSizeV').textContent = `${S.fontSize}px`; save();
      if (fontRenderFrame) cancelAnimationFrame(fontRenderFrame);
      fontRenderFrame = requestAnimationFrame(() => { fontRenderFrame = 0; renderScore(); });
    };
    document.querySelectorAll('[data-bar-pos]').forEach((b) => b.addEventListener('click', () => {
      S.barPosition = b.dataset.barPos; syncControls(); save(); renderScore();
    }));
    $('jump').onsubmit = (e) => { e.preventDefault(); const b = parseInt($('jumpBar').value, 10); if (b) jumpTo(b); };
    $('zoomIn').onclick = () => { S.zoom = Math.min(4, +(S.zoom * 1.25).toFixed(2)); document.documentElement.style.setProperty('--zoom', S.zoom); save(); if (cur) mark(cur, false); };
    $('zoomOut').onclick = () => { S.zoom = Math.max(1, +(S.zoom / 1.25).toFixed(2)); document.documentElement.style.setProperty('--zoom', S.zoom); save(); if (cur) mark(cur, false); };
    $('setBtn').onclick = () => { const s = $('settings'); s.hidden = !s.hidden; $('setBtn').setAttribute('aria-expanded', String(!s.hidden)); };
    document.querySelectorAll('[data-row]').forEach((c) => c.addEventListener('change', () => {
      S.rows[c.dataset.row] = c.checked;
      if (!ROWS.some(([k]) => S.rows[k])) { S.rows[ROWS[0][0]] = true; syncControls(); }
      save(); renderScore();
    }));
    $('sound').onchange = () => { S.sound = $('sound').value; save(); };
    for (const k of ['squeeze', 'fromSel', 'follow', 'metro']) $(k).onchange = () => { S[k] = $(k).checked; save(); };
    $('lines').onchange = () => { S.lines = $('lines').checked; document.body.classList.toggle('nolines', !S.lines); save(); };
    $('practicePlay').onclick = () => {
      const n = byId.get(Number($('practice').dataset.noteId)); if (!n) return;
      if (practiceOsc.length) stopPractice(); else startPractice(n);
    };
    $('practice').addEventListener('close', stopPractice);
    $('infoBtn').onclick = () => $('info').showModal();
    document.addEventListener('keydown', (e) => {
      if (e.target.matches('input,select,textarea') || e.target.closest('.memo-pin') || document.querySelector('dialog[open]')) return;
      if (e.key === ' ' && !e.target.closest('.note') && !e.target.matches('button')) { e.preventDefault(); $('play').click(); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); $('next').click(); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); $('prev').click(); }
    });
  }

  async function init() {
    try {
      const res = await fetch(`data/${encodeURIComponent(PART)}.json`);
      if (!res.ok) throw new Error(`データを読み込めませんでした（${res.status}）`);
      D = await res.json();
    } catch (e) {
      $('err').hidden = false; $('err').textContent = `${e.message}。ページを再読み込みしてください。`; $('title').textContent = 'DYNAMIC'; return;
    }
    D.notes.forEach((n) => { byId.set(n.id, n); const k = n.mvt + ':' + n.bar; if (!mvtNotes.has(k)) mvtNotes.set(k, []); mvtNotes.get(k).push(n.id); });
    ROWS = ROWSETS[D.instrument] || ROWSETS.horn;
    D.showF = D.instrument !== 'trombone' && D.notes.some((n) => n.f[2] !== n.w[2]);
    S.rowsByPart = S.rowsByPart || {};
    S.soundByPart = S.soundByPart || {};
    if (!PRINT) {
      const savedRows = S.rowsByPart[PART] || {};
      S.rows = Object.fromEntries(ROWS.map(([k, , , , , on]) => [k, savedRows[k] === undefined ? on : !!savedRows[k]]));
      S.sound = D.instrument === 'trombone' ? 's' : (S.soundByPart[PART] || S.sound || 's');
    } else if (!params.get('rows')) S.rows = Object.fromEntries(ROWS.map(([k, , , , , on]) => [k, on]));
    else S.rows = Object.fromEntries(ROWS.map(([k]) => [k, params.get('rows').includes(k)]));
    $('rowset').innerHTML = '<legend>表示する行</legend>' + ROWS.map(([k, , , lab, c]) => `<label><input type="checkbox" data-row="${k}"> <b class="${c}">${lab}</b></label>`).join('');
    $('soundWrap').hidden = D.instrument === 'trombone';
    document.title = `${D.title} — DYNAMIC 譜読みアプリ`;
    $('title').textContent = D.title; $('subtitle').textContent = D.subtitle;
    if (D.pdf) { $('pdfLink').hidden = false; $('pdfLink').href = '../' + D.pdf; }
    $('mvts').innerHTML = D.movements.map((m) => `<button role="tab" data-k="${m.key}" aria-selected="false">${MV_NUM[m.key] || m.key}楽章</button>`).join('');
    $('mvts').querySelectorAll('button').forEach((b) => { b.onclick = () => setMvt(b.dataset.k, true); });
    $('infoBody').innerHTML = `<p><b>${esc(D.work)}</b> · ${esc(D.part)}</p><p><span class="badge">要確認あり・第三者監査前</span> ${esc(D.status)}</p><ul class="lim">${D.limitations.map((l) => `<li>${esc(l)}</li>`).join('')}</ul>`;
    syncControls(); wire(); renderScore(); setMvt(D.movements[0].key, false);
    if (PRINT) document.body.classList.add('print');
    window.__dynamic = { data: D, timeline, select, get cur() { return cur; }, get playing() { return !!playing; }, jumpTo,
      ext: { part: PART, print: PRINT, esc, segRange, mvNum: MV_NUM, stop, setMvt, rerender: renderScore, addSvgHook: (f) => { svgHooks.push(f); } } };
    document.dispatchEvent(new Event('dynamic:ready'));
  }
  init();
  if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('../sw.js').catch(() => {});
})();
