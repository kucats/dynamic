/* DYNAMIC reader — metronome for ▶ playback.
 * Pure timing helpers plus a small look-ahead click scheduler. The reader keeps the audio context;
 * this module only reads its clock, so toggling or changing the metronome applies within ~0.1 s. */

// Beat unit from a bar length in whole notes. The reader data keeps the meter as a length only,
// so 4/4 and 2/4 count quarters, 3/8 counts eighths; compound meters (6/8) would count quarters.
export function beatUnit(len) {
  for (const unit of [0.25, 0.125, 0.0625]) {
    const count = len / unit;
    if (Math.abs(count - Math.round(count)) < 1e-6 && Math.round(count) >= 1) return { unit, count: Math.round(count) };
  }
  return { unit: len, count: 1 };
}

// bars: [{ bar, t, len, s }] in playback order (t = bar start in seconds, s = seconds per whole note).
// Returns every beat from `from` on: { t, k (0 = downbeat), n, bar, dur, unit }; count-in beats add ci and left (clicks to go).
export function beatGrid(bars, from = 0, { countIn = false } = {}) {
  const beats = [];
  for (const b of bars) {
    const { unit, count } = beatUnit(b.len), dur = unit * b.s;
    for (let k = 0; k < count; k++) {
      const t = b.t + k * dur;
      if (t >= from - 1e-6) beats.push({ t, k, n: count, bar: b.bar, dur, unit });
    }
  }
  if (!countIn) return beats;
  // One bar of clicks before `from`, on the same grid as the bar being entered.
  const at = [...bars].reverse().find((b) => b.t <= from + 1e-6) || bars[0];
  if (!at) return beats;
  const { unit, count } = beatUnit(at.len), dur = unit * at.s, L = count * dur;
  const pre = [];
  for (let j = Math.ceil((from - L - at.t) / dur - 1e-6); ; j++) {
    const t = at.t + j * dur;
    if (t >= from - 1e-6) break;
    pre.push({ t, k: ((j % count) + count) % count, n: count, bar: at.bar, dur, unit, ci: true });
  }
  pre.forEach((b, i) => { b.left = pre.length - i; });
  return [...pre, ...beats];
}

// A short woodblock-like tick: accent (downbeat), beat, or sub (off-beat).
export function tick(ctx, out, when, kind, vol) {
  const f = kind === 'accent' ? 1760 : kind === 'beat' ? 1175 : 880;
  const peak = vol * (kind === 'accent' ? 0.55 : kind === 'beat' ? 0.38 : 0.2);
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.type = 'triangle'; o.frequency.setValueAtTime(f, when); o.frequency.exponentialRampToValueAtTime(f * 0.72, when + 0.04);
  g.gain.setValueAtTime(0.0001, when); g.gain.exponentialRampToValueAtTime(Math.max(0.0002, peak), when + 0.002);
  g.gain.exponentialRampToValueAtTime(0.0001, when + 0.06);
  o.connect(g); g.connect(out); o.start(when); o.stop(when + 0.07);
  return o;
}

// Schedules clicks for `beats` (times relative to t0 on ctx's clock) a little ahead of time.
// settings() → { on, mode: 'bar' | 'beat' | 'sub', vol } is read at every step.
export function createScheduler(ctx, out, beats, t0, settings, ahead = 0.12) {
  let i = 0, timer = null;
  const live = new Set();
  function step() {
    const until = ctx.currentTime + ahead;
    while (i < beats.length && t0 + beats[i].t < until) {
      const b = beats[i++], when = t0 + b.t;
      if (when < ctx.currentTime - 0.01) continue;
      const s = settings();
      if (!s.on && !b.ci) continue;
      if (s.mode === 'bar' && b.k !== 0 && !b.ci) continue;
      const add = (o) => { live.add(o); o.onended = () => live.delete(o); };
      add(tick(ctx, out, when, b.k === 0 ? 'accent' : 'beat', s.vol));
      if (s.mode === 'sub' && !b.ci) add(tick(ctx, out, when + b.dur / 2, 'sub', s.vol));
    }
  }
  step();
  timer = setInterval(step, 25);
  return {
    stop() { clearInterval(timer); live.forEach((o) => { try { o.stop(); } catch (e) { /* already stopped */ } }); live.clear(); },
    // Latest beat at or before `now` (context time), for the visual indicator.
    current(now) {
      let lo = 0, hi = beats.length - 1, hit = -1;
      while (lo <= hi) { const m = (lo + hi) >> 1; if (t0 + beats[m].t <= now) { hit = m; lo = m + 1; } else hi = m - 1; }
      return hit < 0 ? null : { ...beats[hit], index: hit };
    },
  };
}
