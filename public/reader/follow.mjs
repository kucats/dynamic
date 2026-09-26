import { compileScore, locate, positionLabel, profileMatchesReader, spectralChroma } from './follow-model.mjs';

const NS = 'http://www.w3.org/2000/svg';
const svgElement = (tag, attrs) => { const el = document.createElementNS(NS, tag); for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value); return el; };
const empty = () => ({ status: 'listening', position: null, candidates: [], manual: false });

export function createFollower(api) {
  const panel = document.createElement('section'); panel.className = 'sf-panel'; panel.hidden = true;
  panel.setAttribute('aria-label', '譜面追従（実験）');
  panel.innerHTML = `<div class="sf-head"><strong>譜面追従 · 実験</strong><span class="sf-state" role="status" aria-live="polite"></span><span class="sf-position"></span></div>
    <svg class="sf-map" viewBox="0 0 1000 16" preserveAspectRatio="none" role="img" aria-label="選択中の楽章の位置候補"></svg>
    <div class="sf-candidates" aria-label="位置候補"></div>
    <div class="sf-controls"><button type="button" class="sf-start">マイク開始</button><button type="button" class="sf-reset">再探索</button>
    <form class="sf-jump"><label>現在地 <input type="number" min="1" step="1" inputmode="numeric" required aria-label="追従する小節番号"></label>
    <select aria-label="反復の回数"></select><button type="submit">ここから追う</button></form>
    <label><input type="checkbox" class="sf-scroll" checked> 譜面を送る</label></div>
    <p class="sf-note">ローカル · 音声は保存・送信しません。濃淡は候補の近さで、確率ではありません。手動指定を優先。見失っても直前のテンポで進み、点線と淡い幅で予測を示します。別の場所からやり直すときは現在地の指定か再探索を。合奏の照合は実験中です。</p>`;
  document.getElementById('settings').before(panel);
  const $ = (s) => panel.querySelector(s);
  const state = $('.sf-state'), position = $('.sf-position'), list = $('.sf-candidates'), map = $('.sf-map');
  const start = $('.sf-start'), input = $('.sf-jump input'), occurrence = $('.sf-jump select');
  const reader = { id: api.data.id, movements: api.data.movements, notes: api.data.notes };
  let enabled = false, running = false, pending = false, token = 0, generation = 0, revision = 0;
  let worker = null, busy = false, profile = null, loadProfile = null, movement = api.movement;
  let score = compileScore(reader, movement), result = empty();
  let stream = null, context = null, analyser = null, source = null, timer = null;
  let lastDrawn = '', lastScrolled = null, lastStatus = '', error = '';

  function send(type, rest = {}) { worker?.postMessage({ type, generation, revision, ...rest }); }
  function initWorker() {
    worker?.terminate(); worker = null; busy = false; generation++; revision = 0;
    score = compileScore(reader, movement, profile); input.max = String(Math.max(...score.bars.map((b) => b.bar)));
    worker = new Worker(new URL('./follow-worker.mjs', import.meta.url), { type: 'module' });
    worker.onmessage = ({ data: d }) => {
      busy = false;
      if (!enabled || d.generation !== generation || d.revision !== revision) return;
      result = d.result; draw();
    };
    worker.onerror = () => { stopMic('照合処理を停止しました。「マイク開始」で再試行できます。'); worker?.terminate(); worker = null; };
    send('init', { reader, movement, profile });
  }
  function options() {
    const choices = score.bars.filter((b) => b.bar === Number(input.value));
    occurrence.replaceChildren(...choices.map((b) => { const o = document.createElement('option'); o.value = b.occurrence; o.textContent = `${b.occurrence}回目`; return o; }));
    occurrence.hidden = choices.length < 2;
    input.setCustomValidity(choices.length || !input.value ? '' : '選択中の楽章にない小節です');
  }
  input.oninput = options;
  function override(time, retainPhrase = false) {
    if (!worker) initWorker();
    revision++;
    send('override', { time, retainPhrase });
    result = { ...empty(), status: 'holding', manual: true, position: locate(score, time) };
    error = ''; lastScrolled = null; draw(true);
  }
  $('.sf-jump').onsubmit = (e) => {
    e.preventDefault();
    if (!input.reportValidity()) return;
    const b = score.bars.find((b) => b.bar === Number(input.value) && b.occurrence === Number(occurrence.value));
    if (b) override(b.start);
  };
  $('.sf-reset').onclick = () => { revision++; send('reset'); result = empty(); lastScrolled = null; error = ''; draw(); };
  start.onclick = () => running || pending ? stopMic('停止中 · 現在地を保持') : startMic();

  function stopMic(message = '停止中 · 現在地を保持') {
    token++; running = false; pending = false;
    clearInterval(timer); timer = null;
    stream?.getTracks().forEach((track) => track.stop()); stream = null;
    source?.disconnect(); source = null; analyser = null;
    const old = context; context = null; old?.close().catch(() => {});
    revision++; send('hold'); result = { ...result, status: 'holding', candidates: [] };
    error = message; draw();
  }
  async function startMic() {
    if (!enabled || document.hidden) return;
    if (!navigator.mediaDevices?.getUserMedia || !isSecureContext) { error = 'マイクにはHTTPSと対応ブラウザーが必要です。'; draw(); return; }
    api.ext.stop(); api.ext.stopPractice();
    window.__tuner?.close?.();
    const own = ++token; pending = true; error = ''; draw();
    let acquired = null, localContext = null;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      // Resume inside the button gesture, before the permission/network awaits.
      localContext = new AudioCtx(); context = localContext; await localContext.resume();
      if (own !== token || !enabled || document.hidden) { await localContext.close().catch(() => {}); return; }
      acquired = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
      if (own !== token || !enabled || document.hidden) { acquired.getTracks().forEach((t) => t.stop()); await localContext.close().catch(() => {}); return; }
      if (!worker) initWorker();
      revision++; send('hold'); // AudioContext.currentTime restarts at zero.
      context = localContext; stream = acquired;
      analyser = context.createAnalyser(); analyser.fftSize = 8192; analyser.smoothingTimeConstant = 0;
      source = context.createMediaStreamSource(stream); source.connect(analyser);
      for (const track of stream.getTracks()) track.addEventListener('ended', () => { if (own === token) stopMic('マイクが切断されました。'); });
      context.onstatechange = () => { if (own === token && context?.state !== 'running') stopMic('音声が中断されました。マイク開始で再開できます。'); };
      const db = new Float32Array(analyser.frequencyBinCount), samples = new Float32Array(analyser.fftSize);
      pending = false; running = true; error = ''; draw();
      timer = setInterval(() => {
        if (!running || busy) return;
        analyser.getFloatFrequencyData(db); analyser.getFloatTimeDomainData(samples);
        let energy = 0; for (const x of samples) energy += x * x;
        const chroma = Math.sqrt(energy / samples.length) < .008 ? null : spectralChroma(db, context.sampleRate, analyser.fftSize);
        busy = true; send('frame', { time: context.currentTime - analyser.fftSize / context.sampleRate / 2, chroma });
      }, 200);
    } catch (e) {
      acquired?.getTracks().forEach((t) => t.stop()); localContext?.close().catch(() => {});
      if (own === token) stopMic(e.name === 'NotAllowedError' ? 'マイクの使用が許可されていません。ブラウザーの設定から許可してください。' : 'マイクを開始できませんでした。接続と使用権限を確認してください。');
    }
  }
  function geometry(p) {
    for (const sy of api.data.systems) {
      if (sy.mvt !== movement) continue;
      for (const [xa, xb, label] of sy.segs) {
        if (!label) continue;
        const [a, b] = api.ext.segRange(label);
        if (p.bar < a || p.bar > b) continue;
        const svg = document.querySelector(`#sys-${sy.i} .sc svg`);
        if (!svg) return null;
        const x = xa + (xb - xa) * (p.bar - a) / (b - a + 1), width = (xb - xa) / (b - a + 1);
        return { sy, svg, x, width, cursor: x + width * p.fraction, y: Number(svg.dataset.top) || 0 };
      }
    }
    return null;
  }
  function overlays(scroll = false) {
    document.querySelectorAll('.sf-overlay').forEach((g) => g.remove()); map.replaceChildren();
    const shown = [...result.candidates.map((p, i) => ({ p, alpha: .17 - i * .035, main: false }))];
    if (result.position) shown.push({ p: result.position, alpha: result.status === 'tracking' ? .23 : .11, main: true });
    if (result.position && result.status === 'predicting') {
      for (const b of score.bars) {
        if (b.end < result.position.time - result.uncertainty || b.start > result.position.time + result.uncertainty || b.bar === result.position.bar) continue;
        shown.unshift({ p: locate(score, b.start), alpha: .045, main: false });
      }
    }
    for (const { p, alpha, main } of shown) {
      const geo = geometry(p); if (!geo) continue;
      const { sy, svg, x, width, cursor, y } = geo;
      const g = svgElement('g', { class: 'sf-overlay', 'aria-hidden': 'true' });
      g.append(svgElement('rect', { class: 'sf-region', x, y, width, height: sy.h, opacity: alpha }));
      if (main) g.append(svgElement('line', { class: `sf-cursor${result.status === 'tracking' ? '' : ' sf-held'}`, x1: cursor, x2: cursor, y1: y, y2: y + sy.h }));
      svg.append(g);
      map.append(svgElement('rect', { x: (p.bar - 1) / Number(input.max) * 1000, y: main ? 0 : 4, width: Math.max(4, 1000 / Number(input.max)), height: main ? 16 : 8, fill: '#167ed0', opacity: main ? .85 : .4 }));
      if (main && scroll && $('.sf-scroll').checked) {
        const sc = svg.closest('.sc'), rect = g.getBoundingClientRect(), top = document.getElementById('bar').getBoundingClientRect().bottom + 12;
        if (lastScrolled !== `${p.bar}:${p.occurrence}` && (rect.top < top || rect.bottom > innerHeight - 30)) window.scrollBy({ top: rect.top - top - 20, behavior: 'smooth' });
        const box = sc.getBoundingClientRect();
        const line = g.lastElementChild.getBoundingClientRect();
        if (line.left < box.left + 12 || line.right > box.right - 12) sc.scrollBy({ left: line.left - box.left - box.width * .25, behavior: 'smooth' });
        lastScrolled = `${p.bar}:${p.occurrence}`;
      }
    }
  }
  function draw(forceScroll = false) {
    if (!enabled) return;
    start.textContent = pending ? '許可待ちを中止' : running ? 'マイク停止' : 'マイク開始';
    const text = error || (pending ? 'マイクの許可を待っています' : !running ? 'ローカル · マイク停止中' :
      { listening: 'フレーズの流れを聴いています（最大32秒）', candidates: '候補を選べます', tracking: 'フレーズ追従中（推定）', predicting: `直前のテンポで予測中 · ♩≈${Math.round(result.tempo || 0)}`, holding: '開始待ち · 手動指定した場所から追従します' }[result.status]);
    if (lastStatus !== text) { state.textContent = text; lastStatus = text; }
    position.textContent = result.position ? `${result.manual ? '手動指定を優先 · ' : ''}${positionLabel(score, result.position)}` : '位置未確定';
    const signature = result.candidates.map((p) => `${p.bar}:${p.occurrence}`).join(',');
    if (signature !== lastDrawn && (!result.candidates.length || !list.matches(':focus-within'))) {
      lastDrawn = signature; list.replaceChildren(...result.candidates.map((p, i) => {
        const button = document.createElement('button'); button.type = 'button'; button.textContent = `候補${i + 1} · ${positionLabel(score, p)}`;
        button.title = 'この位置を優先して追従'; button.onclick = () => {
          // Resolve the latest position of this candidate, not an old closure's time.
          const fresh = result.candidates.find((c) => c.bar === p.bar && c.occurrence === p.occurrence);
          override(fresh?.time ?? p.time, true);
        }; return button;
      }));
    }
    overlays(forceScroll || (running && ['tracking', 'predicting'].includes(result.status)));
  }
  api.ext.addBarMenuHook((hit) => enabled && hit.mvt === movement && score.bars.some((b) => b.bar === hit.bar) ? [{ label: 'ここを現在地にして追従', run: () => {
    input.value = hit.bar; options();
    // For a repeated printed bar the explicit occurrence selector is required.
    if (score.bars.filter((b) => b.bar === hit.bar).length > 1) { input.focus(); error = '反復の回数を選んで「ここから追う」を押してください。'; draw(); }
    else override(score.bars.find((b) => b.bar === hit.bar).start);
  } }] : []);
  api.ext.addNoteHook((type) => {
    if (type === 'audio-start' && (running || pending)) stopMic('譜面の再生中は停止しています。');
    if (type === 'movement') {
      stopMic('楽章を変更しました。マイク開始で聴き始めます。'); movement = api.movement;
      worker?.terminate(); worker = null; generation++; score = compileScore(reader, movement, profile); result = empty(); input.value = ''; options();
      lastDrawn = '!'; lastScrolled = null; if (enabled) { initWorker(); draw(); }
    }
    if (type === 'render' && enabled) overlays();
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden && (running || pending)) stopMic('画面を離れたため停止しました。'); });
  window.addEventListener('pagehide', () => stopMic());
  return {
    enable() {
      enabled = true; panel.hidden = false;
      if (!worker) initWorker(); options(); draw();
      // Profiles contain derived notes/marks only; never fetch full score images.
      loadProfile ||= fetch(`following/${encodeURIComponent(api.data.id)}.json`).then((r) => r.ok ? r.json() : null).catch(() => null);
      loadProfile.then((p) => {
        if (!profileMatchesReader(api.data, p) || profile) return;
        profile = p;
        // Do not reset a user's anchor or an active capture when a slow fetch finishes.
        if (enabled && !running && !pending && !result.position) { initWorker(); draw(); }
      });
    },
    disable() { stopMic(); enabled = false; panel.hidden = true; worker?.terminate(); worker = null; generation++; result = empty(); document.querySelectorAll('.sf-overlay').forEach((g) => g.remove()); }
  };
}
