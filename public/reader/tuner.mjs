/* DYNAMIC tuner panel (loaded by tuner-addon.js on first open).
 * The microphone is opened only while the panel is open and running; audio is analysed in this
 * page and never stored or sent anywhere. */
import { detectPitch, noteOf, nameOf } from './tuner-pitch.mjs';

const KEY = 'dynamic-tuner';
const SPAN = 50, SWEEP = 58;                       // ±50 cents across ±58°
const CX = 150, CY = 176, R = 132;
const IN_TUNE = 5, CLOSE = 15, HISTORY_S = 6, HOLD_MS = 700;

const pt = (c, r) => { const a = (c / SPAN) * SWEEP * Math.PI / 180; return [CX + r * Math.sin(a), CY - r * Math.cos(a)]; };
const arc = (c0, c1, r) => { const [x0, y0] = pt(c0, r), [x1, y1] = pt(c1, r); return `M${x0.toFixed(1)} ${y0.toFixed(1)}A${r} ${r} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`; };
const zone = (c) => (Math.abs(c) <= IN_TUNE ? 'ok' : Math.abs(c) <= CLOSE ? 'near' : 'far');

function gaugeSVG() {
  let ticks = '';
  for (let c = -SPAN; c <= SPAN; c += 5) {
    const major = c % 25 === 0, [x0, y0] = pt(c, R - (major ? 14 : 8)), [x1, y1] = pt(c, R);
    ticks += `<line class="${major ? 'tn-maj' : ''}" x1="${x0.toFixed(1)}" y1="${y0.toFixed(1)}" x2="${x1.toFixed(1)}" y2="${y1.toFixed(1)}"/>`;
    if (major) { const [lx, ly] = pt(c, R + 19); ticks += `<text x="${lx.toFixed(1)}" y="${(ly + 4).toFixed(1)}">${c > 0 ? '+' + c : c === 0 ? '0' : '−' + -c}</text>`; }
  }
  const [fx, fy] = pt(-SPAN, R - 30), [sx, sy] = pt(SPAN, R - 30);
  return `<svg class="tn-gauge" viewBox="0 0 300 150" aria-hidden="true">
    <path class="tn-track" d="${arc(-SPAN, SPAN, R)}"/>
    <path class="tn-near" d="${arc(-CLOSE, CLOSE, R)}"/>
    <path class="tn-okband" d="${arc(-IN_TUNE, IN_TUNE, R)}"/>
    <g class="tn-ticks">${ticks}</g>
    <text class="tn-side" x="${fx.toFixed(1)}" y="${fy.toFixed(1)}">♭</text><text class="tn-side" x="${sx.toFixed(1)}" y="${sy.toFixed(1)}">♯</text>
    <g class="tn-needle" style="transform:rotate(0deg)"><line x1="${CX}" y1="${CY - R + 26}" x2="${CX}" y2="${CY - R}"/><circle cx="${CX}" cy="${CY - R}" r="6"/></g>
  </svg>`;
}

export function createTuner({ instrument = 'horn', onClose } = {}) {
  let prefs = { a4: 442, written: false };
  try { prefs = { ...prefs, ...JSON.parse(localStorage.getItem(KEY) || '{}') }; } catch (e) { /* defaults */ }
  if (!(prefs.a4 >= 430 && prefs.a4 <= 450)) prefs.a4 = 442;
  const horn = instrument !== 'trombone';
  const savePrefs = () => { try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (e) { /* ignore */ } };

  const el = document.createElement('section');
  el.className = 'tn'; el.setAttribute('aria-label', 'チューナー'); el.hidden = true;
  const a4s = [];
  for (let f = 436; f <= 446; f++) a4s.push(`<option value="${f}">${f}</option>`);
  el.innerHTML = `<div class="tn-h">
      <b class="tn-title"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M9 2v8.5a3 3 0 0 0 6 0V2M12 13.5V22"/></svg>チューナー</b>
      <label class="tn-a4">A4 <select aria-label="基準ピッチ（A4）">${a4s.join('')}</select> Hz</label>
      ${horn ? '<span class="tn-mode" role="group" aria-label="表示する音"><button type="button" data-w="0">実音</button><button type="button" data-w="1">F管読み</button></span>' : ''}
      <button type="button" class="ghost tn-x" aria-label="チューナーを閉じる">×</button>
    </div>
    <div class="tn-body idle">
      ${gaugeSVG()}
      <div class="tn-note" aria-live="off"><span class="tn-main">–</span><span class="tn-oct"></span></div>
      <div class="tn-subline"><span class="tn-sub">音を出すと表示します</span></div>
      <div class="tn-read"><span class="tn-cents">±0 ¢</span><span class="tn-hz">– Hz</span></div>
      <canvas class="tn-hist" aria-label="直近${HISTORY_S}秒の音程のゆれ"></canvas>
      <div class="tn-foot"><span class="tn-msg" role="status"></span><button type="button" class="tn-run play">マイクを使う</button></div>
    </div>`;
  document.body.append(el);
  const q = (s) => el.querySelector(s);
  const body = q('.tn-body'), needle = q('.tn-needle'), mainEl = q('.tn-main'), octEl = q('.tn-oct'), subEl = q('.tn-sub');
  const centsEl = q('.tn-cents'), hzEl = q('.tn-hz'), msg = q('.tn-msg'), runBtn = q('.tn-run'), hist = q('.tn-hist');
  const a4Sel = q('.tn-a4 select'); a4Sel.value = String(prefs.a4);
  a4Sel.onchange = () => { prefs.a4 = Number(a4Sel.value); savePrefs(); };
  const syncMode = () => el.querySelectorAll('[data-w]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.w === (prefs.written ? '1' : '0'))));
  el.querySelectorAll('[data-w]').forEach((b) => b.addEventListener('click', () => { prefs.written = b.dataset.w === '1'; savePrefs(); syncMode(); last && show(last); }));
  syncMode();
  q('.tn-x').onclick = () => { close(); onClose?.(); };
  runBtn.onclick = () => (stream ? stopMic('一時停止中') : startMic());

  let ctx = null, stream = null, analyser = null, buf = null, raf = 0, lastDetect = 0, lastHeard = 0, last = null;
  let smooth = null, recent = [];
  const trail = [];                                  // [time ms, cents | null, zone]

  function show(r) {
    const name = nameOf(r.midi, instrument, { written: horn && prefs.written });
    mainEl.textContent = name.main; octEl.textContent = String(name.octave);
    subEl.textContent = `${name.sub}${name.octave}${horn ? (prefs.written ? ' · F管読み（実音の完全5度上）' : ' · 実音') : ' · 実音'}`;
    const c = Math.round(r.cents), z = zone(r.cents);
    centsEl.textContent = `${c > 0 ? '+' : c < 0 ? '−' : '±'}${Math.abs(c)} ¢`;
    hzEl.textContent = `${r.freq.toFixed(1)} Hz`;
    body.dataset.zone = z;
    needle.style.transform = `rotate(${(Math.max(-SPAN, Math.min(SPAN, r.cents)) / SPAN) * SWEEP}deg)`;
  }

  function drawTrail(now) {
    const dpr = Math.min(2, window.devicePixelRatio || 1), w = hist.clientWidth, h = hist.clientHeight;
    if (!w || !h) return;
    if (hist.width !== Math.round(w * dpr)) { hist.width = Math.round(w * dpr); hist.height = Math.round(h * dpr); }
    const g = hist.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
    const y = (c) => h / 2 - (Math.max(-SPAN, Math.min(SPAN, c)) / SPAN) * (h / 2 - 3);
    const css = getComputedStyle(el);
    g.fillStyle = css.getPropertyValue('--tn-okbg'); g.fillRect(0, y(IN_TUNE), w, y(-IN_TUNE) - y(IN_TUNE));
    g.strokeStyle = css.getPropertyValue('--tn-grid'); g.lineWidth = 1; g.setLineDash([3, 4]);
    g.beginPath(); g.moveTo(0, h / 2); g.lineTo(w, h / 2); g.stroke(); g.setLineDash([]);
    while (trail.length && now - trail[0][0] > HISTORY_S * 1000) trail.shift();
    const colors = { ok: css.getPropertyValue('--tn-ok'), near: css.getPropertyValue('--tn-nearc'), far: css.getPropertyValue('--tn-far') };
    g.lineWidth = 2.4; g.lineCap = 'round'; g.lineJoin = 'round';
    for (let i = 1; i < trail.length; i++) {
      const [t0, c0] = trail[i - 1], [t1, c1, z] = trail[i];
      if (c0 == null || c1 == null) continue;
      g.strokeStyle = colors[z];
      g.beginPath(); g.moveTo(w - (now - t0) / (HISTORY_S * 1000) * w, y(c0)); g.lineTo(w - (now - t1) / (HISTORY_S * 1000) * w, y(c1)); g.stroke();
    }
  }

  function frame(now) {
    raf = requestAnimationFrame(frame);
    if (analyser && now - lastDetect >= 45) {
      lastDetect = now;
      analyser.getFloatTimeDomainData(buf);
      const r = detectPitch(buf, ctx.sampleRate);
      if (r.freq && r.clarity > 0.75) {
        recent.push(r.freq); if (recent.length > 5) recent.shift();
        const med = [...recent].sort((a, b) => a - b)[recent.length >> 1];
        const n = noteOf(med, prefs.a4);
        // Follow note changes at once; smooth the cents within one note.
        if (!smooth || smooth.midi !== n.midi) smooth = { midi: n.midi, cents: n.cents };
        else smooth.cents += (n.cents - smooth.cents) * 0.35;
        last = { midi: smooth.midi, cents: smooth.cents, freq: med };
        lastHeard = now; body.classList.remove('idle', 'held'); show(last);
        trail.push([now, smooth.cents, zone(smooth.cents)]);
      } else {
        recent = [];
        if (last && now - lastHeard > HOLD_MS) { body.classList.add('held'); smooth = null; }
        trail.push([now, null, 'ok']);
      }
    }
    drawTrail(now);
  }

  async function startMic() {
    if (!navigator.mediaDevices?.getUserMedia) { msg.textContent = 'このブラウザではマイクを使えません（HTTPSが必要です）。'; return; }
    msg.textContent = 'マイクの許可を待っています…'; runBtn.disabled = true;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
    } catch (e) {
      stream = null; runBtn.disabled = false;
      msg.textContent = e && e.name === 'NotAllowedError' ? 'マイクが許可されませんでした。ブラウザの設定で許可してください。' : 'マイクを開始できませんでした。';
      return;
    }
    if (el.hidden) { stopMic(''); return; }         // closed while the permission prompt was up
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    await ctx.resume();
    const src = ctx.createMediaStreamSource(stream);
    analyser = ctx.createAnalyser(); analyser.fftSize = 4096; buf = new Float32Array(analyser.fftSize);
    src.connect(analyser);
    runBtn.disabled = false; runBtn.textContent = '⏸ 一時停止'; runBtn.classList.remove('play'); body.classList.add('live');
    msg.textContent = '聴いています。音はこの端末の中だけで解析し、保存・送信しません。';
    cancelAnimationFrame(raf); raf = requestAnimationFrame(frame);
  }
  function stopMic(text) {
    stream?.getTracks().forEach((t) => t.stop()); stream = null; analyser = null;
    runBtn.disabled = false; runBtn.textContent = '▶ 再開'; runBtn.classList.add('play'); body.classList.remove('live');
    if (last) body.classList.add('held');
    msg.textContent = text;
    cancelAnimationFrame(raf); raf = 0;
    ctx?.suspend().catch(() => {});
  }
  let resumeOnShow = false;
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && stream) { resumeOnShow = true; stopMic('一時停止中'); }
    else if (!document.hidden && resumeOnShow && !el.hidden) { resumeOnShow = false; startMic(); }
  });

  function open() { el.hidden = false; if (!stream) startMic(); return el; }
  function close() { el.hidden = true; resumeOnShow = false; if (stream) stopMic(''); }
  return { el, open, close, get running() { return !!stream; }, get reading() { return last; } };
}
