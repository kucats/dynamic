/* DYNAMIC 譜読みアプリ — reader */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const PART = params.get('part') || 'dvorak8-horn2';
  const PRINT = params.has('print');
  const SIZES = { s: 36, m: 44, l: 56 };
  const ROWS = [['w', 'lw', 1.0], ['f', 'lf', 0.78], ['s', 'ls', 0.64]];
  const MV_NUM = { I: 1, II: 2, III: 3, IV: 4 };

  // ---------- settings (per viewer, optional) ----------
  const DEF = { rows: { w: true, f: false, s: false }, size: 'm', sound: 's', tempo: 100, squeeze: true,
    fromSel: true, follow: true, metro: false, bars: true, lines: true, zoom: innerWidth < 760 ? 2.6 : 1 };
  let S = structuredClone(DEF);
  try { Object.assign(S, JSON.parse(localStorage.getItem('dynamic-settings') || '{}')); } catch (e) { /* ignore */ }
  if (PRINT) { S.zoom = 1; S.rows = { w: params.get('rows') ? params.get('rows').includes('w') : true,
    f: (params.get('rows') || '').includes('f'), s: (params.get('rows') || '').includes('s') }; S.size = params.get('size') || 'm'; }
  const save = () => { if (PRINT) return; try { localStorage.setItem('dynamic-settings', JSON.stringify(S)); } catch (e) { /* ignore */ } };

  let D = null, byId = new Map(), cur = null, playing = null, ctx = null, master = null;

  // ---------- label layout ----------
  function rowWidth(lbl) {           // label width in em (compact metrics)
    const [sol] = lbl; const base = sol.replace(/[♭♯𝄫𝄪]/g, ''); const acc = sol.length - base.length;
    return (base === 'ファ' ? 1.62 : 1.0) + 0.45 * acc + 0.42;
  }
  function labelWidth(n, fs) {
    let w = 0;
    for (const [k, , sc] of ROWS) if (S.rows[k]) w = Math.max(w, rowWidth(k === 'w' ? n.w : k === 'f' ? n.f : n.snd) * sc);
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
  function layout(xs, ws, maxd = 70) {
    const n = xs.length; if (!n) return [[], []];
    let c = place(xs, ws);
    if (Math.max(...c.map((v, i) => Math.abs(v - xs[i]))) <= maxd) return [c, new Array(n).fill(0)];
    const lane = new Array(n).fill(0);
    for (let i = 1; i < n; i++) if (xs[i] - xs[i - 1] < (ws[i] + ws[i - 1]) / 2 + 6) lane[i] = 1 - lane[i - 1];
    c = new Array(n);
    for (const r of [0, 1]) {
      const idx = []; for (let i = 0; i < n; i++) if (lane[i] === r) idx.push(i);
      const cc = place(idx.map((i) => xs[i]), idx.map((i) => ws[i]));
      idx.forEach((i, k) => { c[i] = cc[k]; });
    }
    return [c, lane];
  }
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  function textRow(cls, lbl, x, y, fs) {
    const [sol, oct] = lbl; const base = sol.replace(/[♭♯𝄫𝄪]/g, ''); const acc = sol.slice(base.length);
    const ls = base === 'ファ' ? ' letter-spacing="-0.2em"' : '';
    let t = `<tspan${ls}>${base}</tspan>`;
    if (acc) t += `<tspan font-size="${Math.round(fs * 0.72)}" dx="${Math.round(fs * (ls ? 0.2 : 0.04))}">${acc}</tspan>`;
    else if (ls) t += `<tspan dx="${Math.round(fs * 0.2)}"></tspan>`;
    t += `<tspan font-size="${Math.round(fs * 0.5)}" dy="${-Math.round(fs * 0.42)}">${oct}</tspan>`;
    return `<text class="${cls}" x="${x.toFixed(1)}" y="${y.toFixed(1)}" font-size="${Math.round(fs)}">${t}</text>`;
  }

  // ---------- rendering ----------
  function systemSVG(sy) {
    const fs = SIZES[S.size] || 44, W = sy.w, h = sy.h;
    const ns = D.notes.filter((n) => n.s === sy.i).sort((a, b) => a.x - b.x);
    const ws = ns.map((n) => labelWidth(n, fs));
    const [cx, lane] = layout(ns.map((n) => n.x), ws);
    const lh = labelHeight(fs), strip = 40, laneH = lh + 12;
    const lanes = ns.length ? Math.max(...lane) + 1 : 0;
    const H = h + strip + (ns.length ? lanes * laneH + 10 : 4);
    const o = [`<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="原譜${sy.page}ページ ${sy.sys}段目"><image href="${sy.img}" x="0" y="0" width="${W}" height="${h}"/>`];
    for (const [xa, xb, lab] of sy.segs) {
      o.push(`<line class="bt" x1="${xa}" y1="${h - 8}" x2="${xa}" y2="${h + 30}"/>`);
      if (lab) o.push(`<text class="bn" x="${xa + 8}" y="${h + 28}">${esc(lab)}</text>`);
    }
    const tops = ns.map((n, i) => h + strip + lane[i] * laneH);
    ns.forEach((n, i) => {
      o.push(`<polyline class="leader${n.tie ? ' tie' : ''}" points="${n.x},${(n.y + 20).toFixed(0)} ${n.x},${h + 2} ${cx[i].toFixed(1)},${tops[i].toFixed(1)}"/>`);
    });
    ns.forEach((n, i) => {
      const w = ws[i], top = tops[i];
      let y = top, rows = '';
      for (const [k, cls, sc] of ROWS) {
        if (!S.rows[k]) continue;
        const f = fs * sc; y += f * 0.95;
        rows += textRow(cls, k === 'w' ? n.w : k === 'f' ? n.f : n.snd, cx[i], y, f);
        if (k === 'w' && n.old) rows += `<text class="lw" x="${(cx[i] + w / 2 - fs * 0.18).toFixed(1)}" y="${(y - fs * 0.5).toFixed(1)}" font-size="${Math.round(fs * 0.4)}" fill="#c0392b">※</text>`;
        y += f * 0.13;
      }
      const cls = 'note' + (n.tie ? ' tiec' : '') + (n.unc ? ' unc' : '');
      o.push(`<g class="${cls}" data-id="${n.id}" tabindex="0" role="button" aria-label="${n.bar}小節 ${esc(n.w[0])}${n.w[1]}">`
        + `<rect class="hit" x="${n.x - 34}" y="${n.y - 34}" width="68" height="68"/>`
        + `<ellipse class="halo" cx="${n.x}" cy="${n.y}" rx="30" ry="25"/>`
        + `<rect class="lbg" x="${(cx[i] - w / 2).toFixed(1)}" y="${(top + 2).toFixed(1)}" width="${w.toFixed(1)}" height="${(lh + 4).toFixed(1)}" rx="8"/>`
        + rows + `<rect class="hit" x="${(cx[i] - w / 2).toFixed(1)}" y="${top.toFixed(1)}" width="${w.toFixed(1)}" height="${(lh + 8).toFixed(1)}"/></g>`);
    });
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
    document.body.classList.toggle('nobars', !S.bars);
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
    $('nowF').innerHTML = S.rows.f || D.showF ? `F管 ${esc(n.f[0])}<sup>${n.f[1]}</sup>` : '';
    $('nowS').innerHTML = `実音 ${esc(n.snd[0])}<sup>${n.snd[1]}</sup>`;
    $('nowInfo').textContent = `${MV_NUM[n.mvt] || n.mvt}楽章 ${n.bar}小節 · in ${n.key}${n.tie ? ' · タイの続き' : ''}${n.old ? ' · ヘ音記号は旧記譜' : ''}${n.unc ? ' · 要確認：' + n.unc : ''} · ${id}/${D.notes.length}`;
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
  async function one(n) { await audio(); voice(pitchOf(n), ctx.currentTime + 0.02, 0.65); }

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
    r.setAttribute('class', 'segflash'); r.setAttribute('x', xa); r.setAttribute('y', 0);
    r.setAttribute('width', xb - xa); r.setAttribute('height', sy.h);
    svg.insertBefore(r, svg.children[1]); setTimeout(() => r.remove(), 1800);
  }

  // ---------- wiring ----------
  function syncControls() {
    document.querySelectorAll('[data-row]').forEach((c) => { c.checked = !!S.rows[c.dataset.row]; });
    document.querySelectorAll('input[name=size]').forEach((r) => { r.checked = r.value === S.size; });
    $('sound').value = S.sound; $('tempo').value = S.tempo; $('tempoV').textContent = S.tempo + '%';
    for (const k of ['squeeze', 'fromSel', 'follow', 'metro', 'bars', 'lines']) $(k).checked = !!S[k];
  }
  function wire() {
    $('score').addEventListener('click', (e) => {
      const g = e.target.closest('.note'); if (g) select(+g.dataset.id, { sound: true, scroll: false });
    });
    $('score').addEventListener('keydown', (e) => {
      const g = e.target.closest('.note'); if (g && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); select(+g.dataset.id, { sound: true, scroll: false }); }
    });
    $('play').onclick = () => (playing ? stop() : play());
    $('one').onclick = () => { if (cur) one(byId.get(cur)); else select(D.notes[0].id, { sound: true }); };
    $('prev').onclick = () => select(Math.max(1, (cur || 2) - 1), { sound: true });
    $('next').onclick = () => select(Math.min(D.notes.length, (cur || 0) + 1), { sound: true });
    $('tempo').oninput = () => { S.tempo = +$('tempo').value; $('tempoV').textContent = S.tempo + '%'; save(); };
    $('jump').onsubmit = (e) => { e.preventDefault(); const b = parseInt($('jumpBar').value, 10); if (b) jumpTo(b); };
    $('zoomIn').onclick = () => { S.zoom = Math.min(4, +(S.zoom * 1.25).toFixed(2)); document.documentElement.style.setProperty('--zoom', S.zoom); save(); if (cur) mark(cur, false); };
    $('zoomOut').onclick = () => { S.zoom = Math.max(1, +(S.zoom / 1.25).toFixed(2)); document.documentElement.style.setProperty('--zoom', S.zoom); save(); if (cur) mark(cur, false); };
    $('setBtn').onclick = () => { const s = $('settings'); s.hidden = !s.hidden; $('setBtn').setAttribute('aria-expanded', String(!s.hidden)); };
    document.querySelectorAll('[data-row]').forEach((c) => c.addEventListener('change', () => {
      S.rows[c.dataset.row] = c.checked; if (!S.rows.w && !S.rows.f && !S.rows.s) { S.rows.w = true; syncControls(); } save(); renderScore();
    }));
    document.querySelectorAll('input[name=size]').forEach((r) => r.addEventListener('change', () => { S.size = r.value; save(); renderScore(); }));
    $('sound').onchange = () => { S.sound = $('sound').value; save(); };
    for (const k of ['squeeze', 'fromSel', 'follow', 'metro']) $(k).onchange = () => { S[k] = $(k).checked; save(); };
    $('bars').onchange = () => { S.bars = $('bars').checked; document.body.classList.toggle('nobars', !S.bars); save(); };
    $('lines').onchange = () => { S.lines = $('lines').checked; document.body.classList.toggle('nolines', !S.lines); save(); };
    $('infoBtn').onclick = () => $('info').showModal();
    document.addEventListener('keydown', (e) => {
      if (e.target.matches('input,select,textarea') || $('info').open) return;
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
    D.showF = D.notes.some((n) => n.f[2] !== n.w[2]);
    document.title = `${D.title} — DYNAMIC 譜読みアプリ`;
    $('title').textContent = D.title; $('subtitle').textContent = D.subtitle;
    if (D.pdf) { $('pdfLink').hidden = false; $('pdfLink').href = '../' + D.pdf; }
    $('mvts').innerHTML = D.movements.map((m) => `<button role="tab" data-k="${m.key}" aria-selected="false">${MV_NUM[m.key] || m.key}楽章</button>`).join('');
    $('mvts').querySelectorAll('button').forEach((b) => { b.onclick = () => setMvt(b.dataset.k, true); });
    $('infoBody').innerHTML = `<p><b>${esc(D.work)}</b> · ${esc(D.part)}</p><p><span class="badge">要確認あり・第三者監査前</span> ${esc(D.status)}</p><ul class="lim">${D.limitations.map((l) => `<li>${esc(l)}</li>`).join('')}</ul>`;
    syncControls(); wire(); renderScore(); setMvt(D.movements[0].key, false);
    if (PRINT) document.body.classList.add('print');
    window.__dynamic = { data: D, timeline, select, get cur() { return cur; }, get playing() { return !!playing; }, jumpTo };
    document.dispatchEvent(new Event('dynamic:ready'));
  }
  init();
  if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('../sw.js').catch(() => {});
})();
