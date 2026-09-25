/* DYNAMIC 譜読みアプリ — reader */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const PART = params.get('part') || 'dvorak8-horn2';
  const PRINT = params.has('print');
  const LEGACY_SIZES = { s: 36, m: 44, l: 56 };
  const ROWSETS = {
    horn: [['w', 'lw', 1.0, '記譜ドレミ', 'cw', true], ['f', 'lf', 0.78, 'F管の読み替え', 'cf', false], ['s', 'ls', 0.64, '実音', 'cs', false], ['v', 'lv', 0.8, '運指', 'cv', false]],
    trombone: [['w', 'lw', 1.0, '音名', 'cw', true], ['p', 'lp', 0.8, 'ポジション', 'cp', true]],
  };
  let ROWS = ROWSETS.horn;
  const val = (n, k) => (k === 'w' ? n.w : k === 'f' ? n.f : k === 's' ? n.snd : k === 'v' ? [fingering(n)[0] || '–', '', 0] : [String(n.pos ?? '–'), '', 0]);
  const MV_NUM = { I: 1, II: 2, III: 3, IV: 4 };
  const mvLabel = (k) => { const m = D && D.movements.find((x) => x.key === k); return (m && m.short) || `${MV_NUM[k] || k}楽章`; };

  // ---------- settings (per viewer, optional) ----------
  const DEF = { rows: { w: true, f: false, s: false }, fontSize: 44, barPosition: 'bottom', sound: 's', tempo: 100, squeeze: true,
    fromSel: true, follow: true, metro: false, lines: true, hornMode: 'double', hornSwitch: 69, hornFingeringStyle: 'circles', zoom: innerWidth < 760 ? 2.6 : 1 };
  let S = structuredClone(DEF), storedSettings = {};
  try {
    storedSettings = JSON.parse(localStorage.getItem('dynamic-settings') || '{}');
    Object.assign(S, storedSettings);
    const legacySize = LEGACY_SIZES[storedSettings.size] || DEF.fontSize;
    S.fontSize = Math.max(26, Math.min(72, storedSettings.fontSize == null || !Number.isFinite(Number(storedSettings.fontSize)) ? legacySize : Number(storedSettings.fontSize)));
    if (!['bottom', 'top', 'off'].includes(S.barPosition)) S.barPosition = storedSettings.bars === false ? 'off' : 'bottom';
  } catch (e) { /* ignore */ }
  if (PRINT) {
    S.zoom = 1;
    S.fontSize = LEGACY_SIZES[params.get('size')] || Math.max(26, Math.min(72, Number(params.get('size')) || 44));
    S.barPosition = 'bottom';
  }
  if (!['circles', 'dots'].includes(S.hornFingeringStyle)) S.hornFingeringStyle = DEF.hornFingeringStyle;
  const save = () => {
    if (PRINT) return;
    if (D) {
      S.rowsByPart = S.rowsByPart || {}; S.rowsByPart[PART] = S.rows;
      S.soundByPart = S.soundByPart || {}; S.soundByPart[PART] = S.sound;
    }
    try { localStorage.setItem('dynamic-settings', JSON.stringify(S)); } catch (e) { /* ignore */ }
  };

  const compactToolbar = matchMedia('(max-width:1024px)');
  function syncToolbarLayout() {
    const extras = $('readerExtras'), mount = $('compactExtrasMount'), fieldset = $('compactExtras'), settingsButton = $('setBtn');
    if (!extras || !mount || !fieldset || !settingsButton) return;
    if (compactToolbar.matches) {
      if (extras.parentElement !== mount) mount.appendChild(extras);
      fieldset.hidden = false;
    } else {
      if (extras.parentElement !== settingsButton.parentElement) settingsButton.before(extras);
      fieldset.hidden = true;
    }
  }
  compactToolbar.addEventListener?.('change', syncToolbarLayout);

  const systemHooks = [];             // extensions append content below each system
  const barMenuHooks = [];            // extensions contribute actions for the selected bar
  const svgHooks = [];                // extensions may draw extra SVG per system
  const noteHooks = [];               // extensions (trombone3d-addon.js) follow selection and sound
  const emit = (type, detail) => { for (const f of noteHooks) { try { f(type, detail); } catch (e) { /* an add-on must not break the reader */ } } };
  // ---------- horn fingering aid (general chart, keyed by the F-horn written reading) ----------
  let FG = null;
  function fingering(n) {           // [first choice, ...alternates]; B♭-side fingerings carry a leading 4
    if (!FG || !n.f) return [];
    const m = String(n.f[2]), F = FG.sides.F[m] || [], B = FG.sides.Bb[m] || [];
    const bb = B.map((v) => '4' + v), sw = Number(S.hornSwitch), low = FG.double.lowBb, keepF = FG.double.mostlyBbKeepF;
    if (S.hornMode === 'F') return F;
    // switch 0 = B♭ nearly throughout (GONLOG); otherwise B♭ from the switch note up and in the low C♯3–F3 range (Yamaha)
    const pickBb = sw === 0 ? !keepF.includes(n.f[2]) : n.f[2] >= sw || (n.f[2] >= low[0] && n.f[2] <= low[1]);
    // Avoid 123 (all three valves) when the other side offers another fingering.
    const useBb = B.length && (F[0] === '123' || (pickBb && B[0] !== '123'));
    return useBb ? [...bb, ...F] : [...F, ...bb];
  }

  function fingeringCodeHTML(value) {
    const code = /^[0-4]+$/.test(String(value)) ? String(value) : '–';
    if (S.hornFingeringStyle === 'dots' && code !== '–') {
      const active = new Set(code.split(''));
      return `<span class="fingering-dots" role="img" aria-label="運指 ${esc(code)}">${['4', '3', '2', '1'].map((v) => `<span class="fingering-dot${active.has(v) ? ' on' : ''}"><small>${v}</small><i></i></span>`).join('')}</span>`;
    }
    if (code === '–') return '<span class="fingering-code-empty">–</span>';
    const shape = code.length === 1 ? ' fingering-code-single' : ' fingering-code-combo';
    return `<span class="fingering-code${shape}" role="img" aria-label="運指 ${esc(code)}">${esc(code)}</span>`;
  }
  function fingeringSVG(value, x, y, fs) {
    const code = /^[0-4]+$/.test(String(value)) ? String(value) : '–';
    if (code === '–') return textRow('lv', [code, '', 0], x, y, fs);
    if (S.hornFingeringStyle === 'dots') {
      const valves = ['4', '3', '2', '1'], active = new Set(code.split(''));
      const step = fs * 0.34, r = fs * 0.12, total = step * (valves.length - 1), left = x - total / 2;
      const dots = valves.map((v, i) => {
        const dx = left + i * step, fill = active.has(v) ? ' lv-dot-on' : '';
        return `<text class="lv-dot-label" x="${dx.toFixed(1)}" y="${(y - fs * 0.55).toFixed(1)}" font-size="${Math.max(6, Math.round(fs * 0.22))}">${v}</text><circle class="lv-dot${fill}" cx="${dx.toFixed(1)}" cy="${(y - fs * 0.25).toFixed(1)}" r="${r.toFixed(1)}"/>`;
      }).join('');
      return `<g class="lv-dotset" role="img" aria-label="運指 ${esc(code)}"><title>運指 ${esc(code)}（左から4・3・2・1。塗りつぶしが押す弁）</title>${dots}</g>`;
    }
    const cy = y - fs * 0.34, ry = fs * 0.4, rx = code.length === 1 ? ry : fingeringCodeWidth(code, fs) / 2;
    const ring = `<ellipse class="lv-ring" cx="${x.toFixed(1)}" cy="${cy.toFixed(1)}" rx="${rx.toFixed(1)}" ry="${ry.toFixed(1)}"/>`;
    const digits = `<text class="lv-ring-digit" x="${x.toFixed(1)}" y="${(y + fs * 0.02).toFixed(1)}" font-size="${Math.round(fs * 0.68)}">${esc(code)}</text>`;
    return `<g class="lv-rings" role="img" aria-label="運指 ${esc(code)}"><title>運指 ${esc(code)}</title>${ring}${digits}</g>`;
  }
  function fingeringCodeWidth(code, fontSize) {
    return code.length === 1 ? fontSize * 0.8 : fontSize * (code.length * 0.4 + 0.3);
  }
  function fingeringWidth(n, fontSize) {
    const code = fingering(n)[0] || '–';
    if (code === '–') return fontSize * 0.72;
    return S.hornFingeringStyle === 'dots' ? fontSize * 1.35 : fingeringCodeWidth(code, fontSize);
  }

  let D = null, byId = new Map(), cur = null, playing = null, ctx = null, master = null, practiceOsc = [], practiceTimer = null, fontRenderFrame = 0;

  // ---------- label layout ----------
  function rowWidth(lbl) {           // label width in em (compact metrics)
    const [sol, oct] = lbl; const base = sol.replace(/[♭♯𝄫𝄪]/g, ''); const acc = sol.length - base.length;
    const bw = base === 'ファ' ? 1.62 : /^[A-H]$/.test(base) ? 0.74 : /^[0-9–?]+$/.test(base) ? 0.62 * base.length : 1.0;
    return bw + 0.45 * acc + (oct === '' ? 0.1 : 0.42);
  }
  function labelWidth(n, fs) {
    let w = 0;
    for (const [k, , sc] of ROWS) if (S.rows[k]) w = Math.max(w, k === 'v' ? fingeringWidth(n, fs * sc) / fs : rowWidth(val(n, k)) * sc);
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
    // Focusable measure targets sit behind note hitboxes, preserving note playback.
    if (!PRINT) for (const [xa, xb, lab] of sy.segs) {
      if (!lab) continue;
      o.push(`<rect class="bar-target" data-seg="${esc(lab)}" x="${xa}" y="0" width="${xb - xa}" height="${H}" fill="transparent" tabindex="0" role="button" aria-label="${esc(lab)}小節のメニュー"/>`);
    }
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
      o.push(`<polyline class="leader${n.tie ? ' tie' : ''}${n.sim ? ' simL' : ''}" points="${n.x},${(topBand + n.y + 20).toFixed(0)} ${n.x},${topBand + h + 2} ${cx[i].toFixed(1)},${tops[i].toFixed(1)}"/>`);
    });
    ns.forEach((n, i) => {
      const w = ws[i], top = tops[i], ny = topBand + n.y;
      const fsl = lane[i] ? fs * LOW : fs, lhl = lane[i] ? lh * LOW : lh;
      let y = top, rows = '';
      for (const [k, cls, sc] of ROWS) {
        if (!S.rows[k]) continue;
        const f = fsl * sc; y += f * 0.95;
        rows += k === 'v' ? fingeringSVG(fingering(n)[0] || '–', cx[i], y, f) : textRow(cls, val(n, k), cx[i], y, f);
        if (k === 'w' && n.old) rows += `<text class="lw" x="${(cx[i] + w / 2 - fsl * 0.18).toFixed(1)}" y="${(y - fsl * 0.5).toFixed(1)}" font-size="${Math.round(fsl * 0.4)}" fill="#c0392b">※</text>`;
        y += f * 0.13;
      }
      const cls = 'note' + (n.tie ? ' tiec' : '') + (n.unc ? ' unc' : '') + (n.sim ? ' sim' : '');
      const audioLabel = n.unc ? '。要確認のため音は再生されません' : '。クリックで試聴、ダブルクリックでロングトーン練習';
      o.push(`<g class="${cls}" data-id="${n.id}" tabindex="0" role="button" aria-label="${n.bar}小節 ${esc(n.w[0])}${n.w[1]}${audioLabel}">`
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
    const scrolls = new Map([...main.querySelectorAll('.sys')].map((sec) => [sec.id, sec.querySelector('.sc').scrollLeft]));
    const reviewItems = D.review_items || D.notes.filter((n) => n.unc).map((n) => ({ page: D.systems[n.s].page, bar: n.bar, pitch: n.p, detail: n.unc }));
    const reviewWarning = reviewItems.length
      ? `<div class="print-warning">要確認：${reviewItems.map((r) => `原譜${r.page}ページ ${r.bar}小節 ${esc(r.pitch)} — ${esc(r.detail)}`).join(' ／ ')}（未確定のため音は再生対象外）</div>`
      : '';
    if (PRINT) html.push(`<div class="printhead"><h1>${esc(D.title)}</h1><div>${esc(D.subtitle)} ／ 茶色の数字＝小節番号 ／ 線で音符とつながっています ／ 薄い字＝タイの続き ／ キューには付けていません</div>${reviewWarning}</div>`);
    for (const m of D.movements) {
      html.push(`<h2 class="mv" id="mv-${m.key}">${esc(m.title)} <small>${m.notes}音</small></h2>`);
      for (const sy of D.systems.filter((s) => s.mvt === m.key)) {
        html.push(`<section class="sys" id="sys-${sy.i}" data-mvt="${sy.mvt}"><div class="sc">${systemSVG(sy)}${systemHooks.map((hook) => hook(sy)).join('')}</div></section>`);
      }
    }
    main.innerHTML = html.join('');
    document.body.classList.toggle('nolines', !S.lines);
    document.documentElement.style.setProperty('--zoom', S.zoom);
    // Keep the selected measure visible on phones after memo saves or row changes.
    for (const [id, left] of scrolls) { const sc = $(id)?.querySelector('.sc'); if (sc) sc.scrollLeft = left; }
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
      const overlay = parseFloat(getComputedStyle(document.body).getPropertyValue('--overlay-bottom')) || 0;   // e.g. an add-on panel
      if (r.top < top + 4 || r.bottom > innerHeight - overlay - 10) sec.scrollIntoView({ block: overlay ? 'start' : 'center', behavior: 'smooth' });
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
      const fg = fingering(n);
      $('nowV').innerHTML = S.rows.v && fg.length ? `運指 ${fingeringCodeHTML(fg[0])}${fg.length > 1 ? `<small>（替え ${fg.slice(1).map(fingeringCodeHTML).join('・')}）</small>` : ''}` : '';
    }
    $('nowInfo').textContent = `${mvLabel(n.mvt)} ${n.bar}小節${D.instrument === "trombone" ? "" : " · in " + n.key}${n.tie ? ' · タイの続き' : ''}${n.old ? ' · ヘ音記号は旧記譜' : ''}${n.unc ? ' · 要確認：' + n.unc + '（音は再生しません）' : ''} · ${id}/${D.notes.length}`;
    setMvt(n.mvt, false);
    emit('select', { note: n });
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
  async function one(n, actualSound = true) {
    if (!n || n.unc) return;
    await audio(); voice(actualSound ? n.snd[2] : pitchOf(n), ctx.currentTime + 0.02, 0.85);
    emit('sound', { note: n, delayMs: 0, seconds: 0.85 });
  }

  function stopPractice() {
    clearTimeout(practiceTimer); practiceTimer = null;
    practiceOsc.forEach((o) => { try { o.stop(); } catch (e) { /* already stopped */ } });
    practiceOsc = [];
    emit('silence');
    const button = $('practicePlay');
    if (button) { button.textContent = '▶ ロングトーン'; button.classList.remove('on'); }
  }
  async function startPractice(n) {
    if (!n || n.unc) return;
    stopPractice(); await audio();
    if (!$('practice').open || Number($('practice').dataset.noteId) !== n.id) return;
    const seconds = Number($('practiceDuration').value) || 4;
    practiceOsc = voice(n.snd[2], ctx.currentTime + 0.02, seconds);
    emit('sound', { note: n, delayMs: 0, seconds });
    $('practicePlay').textContent = '■ 停止'; $('practicePlay').classList.add('on');
    practiceTimer = setTimeout(stopPractice, seconds * 1000 + 120);
  }
  function openPractice(id) {
    const n = byId.get(id); if (!n) return;
    stop(); stopPractice(); select(id, { sound: false, scroll: false });
    const pitch = (p) => `${p[0]}${p[1]}`;
    $('practiceWritten').textContent = `譜面：${pitch(n.w)} · ${mvLabel(n.mvt)} ${n.bar}小節`;
    $('practiceSounding').textContent = n.unc ? '吹く音：要確認のため未確定' : `吹く音（実音）：${pitch(n.snd)}`;
    const fg = D.instrument === 'trombone' ? [] : fingering(n);
    $('practiceFingering').innerHTML = S.rows.v && fg.length ? `運指（目安）：${fingeringCodeHTML(fg[0])}${fg.length > 1 ? `　替え ${fg.slice(1).map(fingeringCodeHTML).join('・')}` : ''}` : '';
    $('practice').dataset.noteId = n.id;
    $('practicePlay').disabled = !!n.unc;
    $('practicePlay').textContent = n.unc ? '要確認のため再生不可' : '▶ ロングトーン';
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
      if (n.unc) continue;
      if (!e.d) continue;
      let d = e.d, j = i;
      while (j + 1 < ne.length && !byId.get(ne[j + 1].id).unc && byId.get(ne[j + 1].id).tie) { j++; d = ne[j].t + ne[j].d - e.t; }
      osc.push(...voice(pitchOf(n), t0 + e.t, Math.max(0.05, d * 0.93)));
      emit('sound', { note: n, delayMs: (t0 + e.t - ctx.currentTime) * 1000, seconds: Math.max(0.05, d * 0.93) });
    }
    for (const e of ev) {
      if (e.t < st - 1e-6) continue;
      if (e.m && S.metro) osc.push(...click(t0 + e.t, true));
      const ms = (t0 + e.t - ctx.currentTime) * 1000;
      timers.push(setTimeout(() => {
        if (e.m) $('barNow').textContent = `${mvLabel(mv)} ${e.bar}小節${e.ds ? '（D.S.後）' : ''}`;
        else select(e.id, { scroll: S.follow });
      }, Math.max(0, ms)));
    }
    timers.push(setTimeout(stop, (t0 + total - ctx.currentTime) * 1000 + 300));
    playing = { osc, timers }; $('play').textContent = '■ 停止'; $('play').classList.add('on');
  }
  function stop() {
    if (!playing) return;
    playing.timers.forEach(clearTimeout); playing.osc.forEach((o) => { try { o.stop(); } catch (e) { /* ignore */ } });
    playing = null; emit('silence'); $('play').textContent = '▶ 再生'; $('play').classList.remove('on'); $('barNow').textContent = '';
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
    $('hornMode').value = S.hornMode; $('hornSwitch').value = String(S.hornSwitch); $('hornSwitch').disabled = S.hornMode !== 'double';
    document.querySelectorAll('[name="fingeringStyle"]').forEach((r) => { r.checked = r.value === S.hornFingeringStyle; });
  }
  // ---------- bar context menu / full score ----------
  let viewer = null;
  function loadViewer() {
    if (!viewer) viewer = new Promise((ok, ng) => {
      const s = document.createElement('script'); s.src = 'score-viewer.js';
      s.onload = () => ok(window.DynamicScore); s.onerror = () => { viewer = null; ng(new Error('総譜ビューアを読み込めませんでした')); };
      document.head.appendChild(s);
    });
    return viewer;
  }
  async function openScore(mvt, bar) {
    closeCtx(); stop();
    try { await (await loadViewer()).open({ work: D.work, composer: D.composer, mvt, bar }); }
    catch (e) { $('nowInfo').textContent = e.message; }
  }
  function barAt(e) {                   // bar under the pointer inside a system image, or null
    const svg = e.target.closest('.sc svg'); if (!svg) return null;
    const sec = svg.closest('.sys');
    const sy = D.systems[+sec.id.slice(4)];
    const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const x = pt.matrixTransform(svg.getScreenCTM().inverse()).x;
    const segs = sy.segs.filter((g) => g[2]); if (!segs.length) return null;
    const g = segs.find((q) => x >= q[0] && x < q[1]) || (x < segs[0][0] ? segs[0] : segs.filter((q) => q[0] <= x).pop());
    const [a, b] = segRange(g[2]);
    return { sy, mvt: sy.mvt, bar: a, last: b, seg: g };
  }
  let ctxScroll = null;
  function closeCtx() { const m = $('ctx'); if (m && !m.hidden) m.hidden = true; ctxScroll = null; }
  function openCtx(e, hit) {
    const m = $('ctx'), mv = `${MV_NUM[hit.mvt] || hit.mvt}楽章`;
    const rng = hit.last > hit.bar ? `${hit.bar}〜${hit.last}小節` : `${hit.bar}小節`;
    let selected = hit.bar;
    m.innerHTML = `<div class="ctx-h">${mv} ${rng}</div>`
      + (hit.last > hit.bar ? `<label class="ctx-range">対象の小節 <input type="number" inputmode="numeric" min="${hit.bar}" max="${hit.last}" value="${hit.bar}" step="1" aria-label="休みの中の小節番号"></label>` : '')
      + '<div class="ctx-actions"></div>';
    const actions = m.querySelector('.ctx-actions');
    function renderActions() {
      const valid = Number.isInteger(selected) && selected >= hit.bar && selected <= hit.last;
      const target = { ...hit, bar: selected };
      const extra = valid ? barMenuHooks.flatMap((hook) => hook(target) || []) : [];
      const items = [
        { label: `${valid ? selected : '—'}小節目のスコアを見る`, cls: 'ctx-score', disabled: !valid, run: () => openScore(hit.mvt, selected) },
        ...extra,
        { label: 'この小節から再生', disabled: !valid || !D.notes.some((n) => n.mvt === hit.mvt && n.bar >= selected), run: () => { setMvt(hit.mvt, false); jumpTo(selected); play(); } },
        { label: '閉じる', run: () => {} },
      ];
      actions.replaceChildren(...items.map((item) => {
        const button = document.createElement('button');
        button.type = 'button'; button.textContent = item.label;
        button.className = item.cls || ''; button.disabled = !!item.disabled;
        button.setAttribute('role', 'menuitem');
        button.onclick = () => { closeCtx(); item.run(); };
        return button;
      }));
    }
    m.querySelector('input')?.addEventListener('input', (ev) => { selected = ev.target.valueAsNumber; renderActions(); });
    m.onclick = null; renderActions(); m.hidden = false;
    ctxScroll = { x: scrollX, y: scrollY };
    const r = m.getBoundingClientRect();
    m.style.left = `${Math.max(8, Math.min(e.clientX, innerWidth - r.width - 8))}px`;
    m.style.top = `${Math.max(8, Math.min(e.clientY, innerHeight - r.height - 8))}px`;
    m.querySelector('.ctx-score').focus({ preventScroll: true });
    m.onkeydown = (ev) => {
      if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(ev.key) || ev.target.matches('input')) return;
      const buttons = [...m.querySelectorAll('button:not(:disabled)')];
      const i = buttons.indexOf(document.activeElement);
      const next = ev.key === 'Home' ? 0 : ev.key === 'End' ? buttons.length - 1 : (i + (ev.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
      ev.preventDefault(); buttons[next]?.focus();
    };
    flash(hit.sy, hit.seg[0], hit.seg[1]);
  }

  function wire() {
    $('score').addEventListener('click', (e) => {
      const g = e.target.closest('.note');
      if (!g) { const hit = barAt(e); if (hit) openCtx(e, hit); return; }
      if (e.detail >= 2) { e.preventDefault(); openPractice(+g.dataset.id); return; }
      select(+g.dataset.id, { sound: true, scroll: false });
    });
    $('score').addEventListener('dblclick', (e) => {
      const g = e.target.closest('.note'); if (g) { e.preventDefault(); openPractice(+g.dataset.id); }
    });
    $('score').addEventListener('contextmenu', (e) => {
      const g = e.target.closest('.note'); if (g) { e.preventDefault(); openPractice(+g.dataset.id); return; }
      const hit = barAt(e); if (hit) { e.preventDefault(); openCtx(e, hit); }
    });
    document.addEventListener('pointerdown', (e) => { if (!e.target.closest('#ctx')) closeCtx(); }, true);
    // Focus can queue a scroll event before Enter opens the menu. Dismiss only
    // when the viewport actually moves after opening, not for that queued event.
    addEventListener('scroll', () => {
      if (ctxScroll && (scrollX !== ctxScroll.x || scrollY !== ctxScroll.y)) closeCtx();
    }, { passive: true });
    $('scoreBtn').onclick = () => {
      const n = cur && byId.get(cur);
      const typed = parseInt($('jumpBar').value, 10);
      openScore(n ? n.mvt : currentMvt, n ? n.bar : typed || 1);
    };
    $('score').addEventListener('keydown', (e) => {
      const target = e.target.closest('.bar-target');
      if (target && (e.key === 'Enter' || e.key === ' ')) {
        e.preventDefault(); e.stopPropagation();
        const sy = D.systems[+target.closest('.sys').id.slice(4)];
        const seg = sy.segs.find((g) => g[2] === target.dataset.seg), [bar, last] = segRange(seg[2]);
        const r = target.getBoundingClientRect();
        openCtx({ clientX: Math.max(8, r.left), clientY: Math.max($('bar').getBoundingClientRect().bottom + 8, r.top) }, { sy, mvt: sy.mvt, bar, last, seg });
        return;
      }
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
    $('zoomOut').onclick = () => { S.zoom = Math.max(0.5, +(S.zoom / 1.25).toFixed(2)); document.documentElement.style.setProperty('--zoom', S.zoom); save(); if (cur) mark(cur, false); };
    $('setBtn').onclick = () => { const s = $('settings'); s.hidden = !s.hidden; $('setBtn').setAttribute('aria-expanded', String(!s.hidden)); };
    document.querySelectorAll('[data-row]').forEach((c) => c.addEventListener('change', () => {
      S.rows[c.dataset.row] = c.checked;
      if (!ROWS.some(([k]) => S.rows[k])) { S.rows[ROWS[0][0]] = true; syncControls(); }
      save(); renderScore(); if (cur) select(cur, { scroll: false });
    }));
    $('sound').onchange = () => { S.sound = $('sound').value; save(); };
    const refingering = () => { syncControls(); save(); renderScore(); if (cur) select(cur, { scroll: false }); };
    $('hornMode').onchange = () => { S.hornMode = $('hornMode').value; refingering(); };
    $('hornSwitch').onchange = () => { S.hornSwitch = Number($('hornSwitch').value); refingering(); };
    document.querySelectorAll('[name="fingeringStyle"]').forEach((r) => r.addEventListener('change', () => {
      if (!r.checked) return;
      S.hornFingeringStyle = r.value; refingering();
    }));
    for (const k of ['squeeze', 'fromSel', 'follow', 'metro']) $(k).onchange = () => { S[k] = $(k).checked; save(); };
    $('lines').onchange = () => { S.lines = $('lines').checked; document.body.classList.toggle('nolines', !S.lines); save(); };
    $('practicePlay').onclick = () => {
      const n = byId.get(Number($('practice').dataset.noteId)); if (!n) return;
      if (n.unc) return;
      if (practiceOsc.length) stopPractice(); else startPractice(n);
    };
    $('practice').addEventListener('close', stopPractice);
    $('infoBtn').onclick = () => $('info').showModal();
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeCtx();
      if (e.target.matches('input,select,textarea') || e.target.closest('.memo-card,.bar-target,#ctx') || $('info').open || $('practice').open || document.querySelector('dialog[open]') || document.documentElement.classList.contains('sv-open')) return;
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
    if (D.instrument !== 'trombone') {
      try { const r = await fetch('horn-fingerings.json'); if (r.ok) FG = await r.json(); } catch (e) { /* fingering row shows – */ }
      if (FG) {
        const names = FG.names || {};
        // Migrate the earlier hornSwitchAt setting. Its zero value meant the Yamaha chart order,
        // which is the same as this chart's default; it did not mean the new mostly-B♭ mode.
        if (storedSettings.hornSwitch == null && storedSettings.hornSwitchAt != null) {
          const oldSwitch = Number(storedSettings.hornSwitchAt);
          S.hornSwitch = oldSwitch === 0 ? FG.switch.default : oldSwitch;
        }
        $('hornSwitch').innerHTML = FG.switch.choices.map((m) => `<option value="${m}">${esc(FG.switch.labels?.[m] || (names[m] || m).replace('#', '♯').replace('b', '♭') + 'から')}</option>`).join('');
        if (!FG.switch.choices.includes(Number(S.hornSwitch))) S.hornSwitch = FG.switch.default;
      }
      if (PRINT) { if (params.get('horn') === 'F') S.hornMode = 'F'; if (params.get('switch')) S.hornSwitch = Number(params.get('switch')); }
    }
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
    $('fingerset').hidden = D.instrument === 'trombone' || !FG;
    document.title = `${D.title} — DYNAMIC 譜読みアプリ`;
    $('title').textContent = D.title; $('subtitle').textContent = D.subtitle;
    if (D.pdf) { $('pdfLink').hidden = false; $('pdfLink').href = '../' + D.pdf; }
    $('mvts').innerHTML = D.movements.map((m) => `<button role="tab" data-k="${m.key}" aria-selected="false">${esc(mvLabel(m.key))}</button>`).join('');
    $('mvts').querySelectorAll('button').forEach((b) => { b.onclick = () => setMvt(b.dataset.k, true); });
    $('infoBody').innerHTML = `<p><b>${esc(D.work)}</b> · ${esc(D.part)}</p><p><span class="badge">要確認あり・第三者監査前</span> ${esc(D.status)}</p><ul class="lim">${D.limitations.map((l) => `<li>${esc(l)}</li>`).join('')}</ul>`;
    syncToolbarLayout(); syncControls(); wire(); renderScore(); setMvt(D.movements[0].key, false);
    if (PRINT) document.body.classList.add('print');
    window.__dynamic = { data: D, timeline, select, get cur() { return cur; }, get playing() { return !!playing; }, jumpTo,
      openScore,
      ext: { part: PART, print: PRINT, esc, segRange, mvNum: MV_NUM, stop, setMvt, rerender: renderScore, addSystemHook: (f) => { systemHooks.push(f); }, addBarMenuHook: (f) => { barMenuHooks.push(f); }, addSvgHook: (f) => { svgHooks.push(f); }, addNoteHook: (f) => { noteHooks.push(f); } } };
    document.dispatchEvent(new Event('dynamic:ready'));
  }
  init();
  if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('../sw.js').catch(() => {});
})();
