/* DYNAMIC reader — conductor for ▶ playback.
 * Decides how many beats a conductor gives per bar (in 1 / in 2 / in 3 / in 4 / in 6), builds the
 * beat grid on the same clock as the metronome, and computes the baton-tip position for drawing.
 * The reader draws; this module has no DOM access. */

import { beatUnit } from './metronome.mjs';

export const PATTERNS = [1, 2, 3, 4, 6];

// Meter string ("6/8") → { num, den }; null when the data has no meter string.
export function parseMeter(m) {
  const x = /^(\d+)\/(\d+)$/.exec(String(m || ''));
  return x ? { num: +x[1], den: +x[2] } : null;
}

// Default pattern from the meter and the tempo (s = seconds per whole note).
// A tempo-based estimate only: fast bars go "in 1" or "in 2", very slow ones are subdivided.
export function autoPattern(len, s, meter = null) {
  const q = 60 / (0.25 * s), e = 2 * q;             // quarter and eighth beats per minute
  if (meter && meter.den === 8 && meter.num % 3 === 0 && meter.num > 3) {   // compound: 6/8, 9/8, 12/8
    const groups = meter.num / 3;
    return e >= 132 ? groups : (groups === 2 ? 6 : groups);
  }
  const { count, unit } = beatUnit(len);
  const bpm = unit === 0.125 ? e : unit === 0.0625 ? 4 * q : q;
  if (count === 1) return 1;
  if (count === 2) return bpm >= 120 ? 1 : bpm < 56 ? 4 : 2;
  if (count === 3) return bpm >= 144 ? 1 : 3;
  if (count === 4) return bpm >= 132 ? 2 : 4;
  if (count === 6) return bpm >= 132 ? 2 : 6;
  // Irregular meters (5/8, 7/8) need uneven groupings, which this grid does not model: one per bar.
  return count % 4 === 0 ? 4 : count % 3 === 0 ? 3 : count % 2 === 0 ? 2 : 1;
}

// Latest [bar, value] entry at or before `bar`, or null.
export function planAt(pairs, bar) {
  let v = null;
  for (const [b, x] of pairs || []) if (b <= bar) v = x;
  return v;
}

// Pattern for one bar: a forced choice (1–6) wins when it fits the bar, then the part's
// annotated plan, then the tempo estimate. Returns { n, src: 'forced' | 'plan' | 'auto' }.
export function patternFor(bar, { len, s, meter = null, plan = null, force = 'auto' }) {
  const n = Number(force);
  if (PATTERNS.includes(n)) {
    const { count } = beatUnit(len);
    if (count % n === 0 || n % count === 0 || (meter && meter.num % n === 0)) return { n, src: 'forced' };
  }
  const p = Number(planAt(plan, bar));
  if (PATTERNS.includes(p)) return { n: p, src: 'plan' };
  return { n: autoPattern(len, s, meter), src: 'auto' };
}

// bars: [{ bar, t, len, s }] in playback order; pick(bar) → { n, src }.
// Returns every conducting beat from `from` on: { t, k (0 = downbeat), n, bar, dur, src };
// with lead > 0, preparatory beats (pre: true) on the entered bar's pattern fill `lead` seconds before `from`.
export function conductGrid(bars, pick, from = 0, lead = 0) {
  const beats = [];
  for (const b of bars) {
    const { n, src } = pick(b), dur = (b.len * b.s) / n;
    for (let k = 0; k < n; k++) {
      const t = b.t + k * dur;
      if (t >= from - 1e-6) beats.push({ t, k, n, bar: b.bar, dur, src });
    }
  }
  if (!(lead > 0)) return beats;
  const at = [...bars].reverse().find((b) => b.t <= from + 1e-6) || bars[0];
  if (!at) return beats;
  const { n, src } = pick(at), dur = (at.len * at.s) / n, pre = [];
  for (let j = Math.ceil((from - lead - at.t) / dur - 1e-6); ; j++) {
    const t = at.t + j * dur;
    if (t >= from - 1e-6) break;
    pre.push({ t, k: ((j % n) + n) % n, n, bar: at.bar, dur, src, pre: true });
  }
  return [...pre, ...beats];
}

// Index of the latest beat at or before `t` (binary search), or -1.
export function beatAt(beats, t) {
  let lo = 0, hi = beats.length - 1, hit = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (beats[m].t <= t) { hit = m; lo = m + 1; } else hi = m - 1; }
  return hit;
}

// Next bar (after beat i) whose pattern differs, for the "next: in 4" hint.
export function nextChange(beats, i) {
  if (i < 0 || i >= beats.length) return null;
  const n = beats[i].n;
  for (let j = i + 1; j < beats.length; j++) if (!beats[j].pre && beats[j].n !== n && beats[j].k === 0) return beats[j];
  return null;
}

// Ictus points of the standard patterns: x in [-1, 1] (right = +), y in [0, 1] (down = +).
// h = rebound height after that beat. Beat 1 always falls straight down to the centre.
const ICTUS = {
  1: [{ x: 0, y: 0.9, h: 0.72 }],
  2: [{ x: -0.04, y: 0.9, h: 0.42 }, { x: 0.36, y: 0.8, h: 0.62 }],
  3: [{ x: -0.04, y: 0.9, h: 0.3 }, { x: 0.58, y: 0.8, h: 0.34 }, { x: 0.3, y: 0.52, h: 0.42 }],
  4: [{ x: 0, y: 0.9, h: 0.26 }, { x: -0.58, y: 0.76, h: 0.26 }, { x: 0.62, y: 0.55, h: 0.22 }, { x: 0, y: 0.16, h: 0.4 }],
  6: [{ x: 0, y: 0.9, h: 0.2 }, { x: -0.3, y: 0.83, h: 0.14 }, { x: -0.62, y: 0.76, h: 0.3 },
    { x: 0.34, y: 0.82, h: 0.16 }, { x: 0.66, y: 0.77, h: 0.28 }, { x: 0.3, y: 0.52, h: 0.42 }],
};
export const ictus = (n, k) => (ICTUS[n] || ICTUS[4])[k % (ICTUS[n] || ICTUS[4]).length];

// The audience sees the conductor's left/right reversed; mirror shows the conductor's view.
export const displayX = (x, mirror = false) => mirror ? x : -x;

const smooth = (p) => p * p * (3 - 2 * p);

// Baton tip between ictus a and ictus b at phase p ∈ [0, 1): a parabola (gravity-like fall into
// the next beat), horizontal motion eased.
export function between(a, b, p) {
  p = Math.max(0, Math.min(1, p));
  return { x: a.x + (b.x - a.x) * smooth(p), y: a.y + (b.y - a.y) * p - a.h * 4 * p * (1 - p) };
}

// Baton tip at time t for a grid: before the first beat the baton waits at the top (preparation).
export function tipAt(beats, t) {
  const i = beatAt(beats, t);
  if (i < 0) {
    if (!beats.length) return { x: 0, y: 0.2, i };
    const b = beats[0], a = { x: 0.3, y: 0.3, h: 0.1 }, p = 1 - Math.min(1, (b.t - t) / b.dur);
    return { ...between(a, ictus(b.n, b.k), p), i };
  }
  const cur = beats[i], nx = beats[i + 1];
  const a = ictus(cur.n, cur.k);
  const b = nx && nx.t - cur.t < cur.dur * 1.5 + 1e-6 ? ictus(nx.n, nx.k) : ictus(cur.n, 0);
  return { ...between(a, b, (t - cur.t) / cur.dur), i };
}

// One bar of the pattern as a polyline, for the faint guide drawing.
export function guide(n, steps = 16) {
  const pts = [];
  for (let k = 0; k < n; k++) {
    const a = ictus(n, k), b = ictus(n, (k + 1) % n);
    for (let j = 0; j < steps; j++) pts.push(between(a, b, j / steps));
  }
  pts.push(ictus(n, 0));
  return pts;
}
