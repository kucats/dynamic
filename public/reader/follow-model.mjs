// Experimental phrase matching. Scores are similarities, NEVER probabilities.
// All clocks below are audio seconds; score time uses the uncompressed timeline.
import { alignPhrase } from './follow-alignment.mjs';
export const STEP = 0.2;
const SPEEDS = [0.6, 0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.35, 1.5];
const popcount = (n) => { let k = 0; for (; n; n &= n - 1) k++; return k; };
const contextualMatch = (c) => ['context-dtw', 'event-sequence'].includes(c?.method);

export function profileMatchesReader(reader, profile) {
  if (profile?.schema !== 2 || profile.id !== reader.id ||
      profile.sources?.[reader.id]?.sha256 !== reader.source?.sha256) return false;
  return reader.movements.every((m) => {
    const source = profile.movements?.[m.key];
    if (!source || JSON.stringify(source.timeline) !== JSON.stringify(m.timeline)) return false;
    const current = reader.notes.filter((n) => n.mvt === m.key && !n.unc)
      .map((n) => [n.bar, n.off, n.dur, n.snd[2], !!n.tie, reader.id, n.id]);
    return JSON.stringify(current) === JSON.stringify(source.notes.filter((n) => n[5] === reader.id));
  });
}

export function compileScore(data, movement, profile = null) {
  const m = data.movements.find((v) => v.key === movement);
  if (!m) throw new Error('楽章が見つかりません');
  const source = profile?.movements?.[movement];
  const notes = source?.notes || data.notes.filter((n) => n.mvt === movement && !n.unc)
    .map((n) => [n.bar, n.off, n.dur, n.snd[2], n.tie, data.id, n.id]);
  const byBar = new Map();
  for (const n of notes) { if (!byBar.has(n[0])) byBar.set(n[0], []); byBar.get(n[0]).push(n); }
  let duration = 0, quarter = 0;
  const occurrences = new Map(), bars = [], spans = [];
  for (const [bar, len, seconds] of m.timeline) {
    const occurrence = (occurrences.get(bar) || 0) + 1;
    occurrences.set(bar, occurrence);
    bars.push({ bar, occurrence, start: duration, end: duration + len * seconds, quarter, quarters: len * 4, seconds });
    for (const n of byBar.get(bar) || []) {
      // snd is already concert pitch; do not transpose a second time.
      if (!Number.isFinite(n[3]) || n[2] <= 0) continue;
      spans.push({ start: duration + n[1] * seconds, end: duration + Math.min(len, n[1] + n[2]) * seconds,
        mask: 1 << ((n[3] % 12 + 12) % 12), attack: !n[4] });
    }
    duration += len * seconds;
    quarter += len * 4;
  }
  const masks = new Uint16Array(Math.ceil(duration / STEP));
  const attacks = new Uint8Array(masks.length);
  for (const s of spans) {
    for (let i = Math.max(0, Math.ceil(s.start / STEP - .5)); i < masks.length && (i + .5) * STEP < s.end; i++) masks[i] |= s.mask;
    if (s.attack) attacks[Math.min(attacks.length - 1, Math.floor(s.start / STEP))] = 1;
  }
  return { movement, duration, bars, masks, attacks, rehearsals: source?.rehearsals || [] };
}

export function locate(score, time) {
  const t = Math.max(0, Math.min(score.duration - .001, time));
  let lo = 0, hi = score.bars.length - 1;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (score.bars[mid].end <= t) lo = mid + 1; else hi = mid; }
  const b = score.bars[lo];
  return { ...b, time: t, fraction: (t - b.start) / (b.end - b.start) };
}

function advance(score, start, elapsed, tempo) {
  const p = locate(score, start);
  const quarter = p.quarter + p.fraction * p.quarters + elapsed * tempo / 60;
  const b = score.bars.find((v) => v.quarter + v.quarters > quarter);
  return b ? locate(score, b.start + (quarter - b.quarter) * b.seconds / 4) : locate(score, score.duration);
}

export function positionLabel(score, p) {
  const mark = score.rehearsals.reduce((best, r) => !best || Math.abs(r.bar - p.bar) < Math.abs(best.bar - p.bar) ? r : best, null);
  const offset = mark ? p.bar - mark.bar : 0;
  const repeat = score.bars.filter((b) => b.bar === p.bar).length > 1 ? `・${p.occurrence}回目` : '';
  return `${mark ? `練習${mark.label}${offset ? `${offset > 0 ? '＋' : '−'}${Math.abs(offset)}` : ''} · ` : ''}${p.bar}小節${repeat}`;
}

// Whiten local spectral peaks before folding into pitch classes. A loud bass or
// microphone frequency response should not dominate every comparison. No f0 is
// forced on polyphonic audio. Flat/noisy spectra return null.
export function spectralChroma(db, sampleRate, fftSize, a4 = 442) {
  const values = new Float32Array(12);
  let peakiness = 0;
  for (let midi = 36; midi <= 95; midi++) {
    const f = a4 * 2 ** ((midi - 69) / 12), bin = f * fftSize / sampleRate;
    const a = Math.max(1, Math.floor(bin * .977)), b = Math.min(db.length - 1, Math.ceil(bin * 1.023));
    let peak = -140;
    for (let i = a; i <= b; i++) peak = Math.max(peak, Number.isFinite(db[i]) ? db[i] : -140);
    const l = Math.max(1, Math.floor(bin * .9)), r = Math.min(db.length - 1, Math.ceil(bin * 1.1));
    let floor = 0, count = 0;
    for (let i = l; i <= r; i++) if (i < a || i > b) { floor += Number.isFinite(db[i]) ? db[i] : -140; count++; }
    const prominence = Math.max(0, Math.min(24, peak - floor / Math.max(1, count) - 4));
    const value = prominence * Math.max(0, Math.min(1, (peak + 85) / 35));
    values[midi % 12] += value;
    peakiness += value;
  }
  if (peakiness < 15) return null;
  const mean = values.reduce((a, b) => a + b, 0) / 12;
  let norm = 0;
  for (let i = 0; i < 12; i++) { values[i] -= mean; norm += values[i] ** 2; }
  if (norm < 10) return null;
  norm = Math.sqrt(norm);
  return Float32Array.from(values, (v) => v / norm);
}

export class PhraseMatcher {
  constructor(score) { this.score = score; this.reset(); }
  reset() { this.frames = []; this.anchor = null; this.pending = null; this.lastSearch = -Infinity; this.lastTime = -Infinity; this.lastFeatureTime = -Infinity; this.result = this.snapshot('listening', []); }
  snapshot(status, candidates) {
    const elapsed = this.anchor && this.anchor.at != null && Number.isFinite(this.lastTime) ? Math.max(0, this.lastTime - this.anchor.at) : 0;
    const sinceEvidence = this.anchor?.evidenceAt != null && Number.isFinite(this.lastTime) ? Math.max(0, this.lastTime - this.anchor.evidenceAt) : elapsed;
    const predicted = status === 'predicting';
    return { status, candidates, position: this.anchor ? advance(this.score, this.anchor.time, elapsed, this.anchor.tempo) : null,
      manual: !!this.anchor?.manual, uncertainty: predicted ? Math.min(20, .4 + sinceEvidence * .3) : .2,
      tempo: this.anchor?.tempo || null };
  }
  override(time, at = this.lastTime, retainPhrase = false) {
    const p = locate(this.score, time);
    this.anchor = { time: p.time, at: Number.isFinite(at) ? at : null, evidenceAt: Number.isFinite(at) ? at : null,
      manual: true, tempo: this.anchor?.tempo || 240 / p.seconds };
    this.pending = null;
    if (!retainPhrase) this.frames = [];
    this.result = this.snapshot('holding', []);
    return this.result;
  }
  hold() {
    // An explicit stop freezes the current estimate and starts a new audio clock.
    const p = this.snapshot('holding', []).position;
    if (this.anchor) { this.anchor.time = p.time; this.anchor.at = null; this.anchor.evidenceAt = null; }
    this.frames = []; this.pending = null; this.lastTime = -Infinity; this.lastSearch = -Infinity; this.lastFeatureTime = -Infinity;
    this.result = this.snapshot(this.anchor ? 'holding' : 'listening', []); return this.result;
  }
  remember(time, chroma) {
    this.frames.push({ time, chroma });
    this.frames = this.frames.filter((f) => time - f.time <= 32);
    // Leading silence is not a musical prefix. Interior rests keep their time.
    while (this.frames.length && !this.frames[0].chroma) this.frames.shift();
  }
  push(time, chroma) {
    if (!Number.isFinite(time) || time <= this.lastTime) return this.result;
    if (time - this.lastTime > .65) { this.frames = []; this.pending = null; } // capture gaps never count as a phrase
    else if (time - this.lastTime > STEP * 1.6) {
      for (let t = this.lastTime + STEP; t < time - STEP * .5; t += STEP) this.remember(t, null);
    }
    this.lastTime = time;
    if (this.anchor?.at == null && this.anchor) { this.anchor.at = time; this.anchor.evidenceAt = time; }
    if (!chroma) {
      // Keep bounded context across rests, but never count silence as fresh
      // acoustic support. Time is retained so the next phrase cannot collapse
      // an intervening rest into a single instant.
      this.remember(time, null);
      if (time - this.lastFeatureTime > 1.2) this.pending = null;
      return this.result = this.snapshot(this.anchor ? 'predicting' : 'listening', []);
    }
    this.lastFeatureTime = time;
    this.remember(time, chroma);
    if (time - this.lastSearch < .55 || this.frames.length < 14 || time - this.frames[0].time < 3.8)
      return this.result = this.snapshot(this.anchor ? (time - this.anchor.at > .7 ? 'predicting' : this.result.status) : this.result.status, this.result.candidates);
    this.lastSearch = time;
    let changes = 0, previous = this.frames.find((f) => f.chroma);
    for (const f of this.frames) {
      if (!f.chroma) continue;
      if (f.time - previous.time < .35) continue;
      const dot = f.chroma.reduce((sum, v, k) => sum + v * previous.chroma[k], 0);
      if (dot < .9) { changes++; previous = f; }
    }
    if (changes < 3) return this.result = this.snapshot(this.anchor ? 'predicting' : 'listening', []);
    const matches = this.search(time);
    const candidates = [];
    for (const c of matches) if (c.score >= (contextualMatch(c) ? .25 : .38) && candidates.every((p) => Math.abs(p.time - c.time) > 2.4)) {
      candidates.push({ ...locate(this.score, c.time), score: c.score, speed: c.speed, context: c.context || 0 });
      if (candidates.length === 3) break;
    }
    let best = matches[0];
    if (this.anchor) {
      const predicted = this.snapshot('predicting', []).position.time;
      const radius = Math.min(12, 1.5 + Math.max(0, time - this.anchor.at) * .25);
      // Always search near the projected path, even after a long outage.
      best = matches.find((c) => Math.abs(c.time - predicted) <= radius);
    }
    const distant = best && candidates.find((c) => Math.abs(c.time - best.time) > 2.4);
    const contextual = contextualMatch(best);
    const clear = best && best.score >= (contextual ? .30 : .48) && best.recent >= .22 &&
      (this.anchor || !distant || best.score - distant.score > (contextual ? .035 : .07)) &&
      (this.anchor || this.score.duration < 20 || contextual);
    if (clear) {
      const progress = this.pending ? (best.time - this.pending.time) / (time - this.pending.at) : null;
      if (this.pending && progress >= .25 && progress <= 2.2) {
        this.pending.count++;
      } else this.pending = { time: best.time, count: 1 };
      this.pending.time = best.time; this.pending.at = time;
      if (this.pending.count >= (this.anchor ? 2 : contextual ? 5 : 3)) {
        const predicted = this.snapshot('predicting', []).position?.time;
        // Correct phase gradually, without rewinding the display or snapping
        // several measures forward. Tempo is smoothed independently of phase.
        const previous = this.result.position?.time ?? 0;
        const next = predicted == null ? best.time : Math.max(previous, predicted + Math.max(-.15, Math.min(.2, best.time - predicted)));
        const measured = best.speed * 240 / locate(this.score, best.time).seconds;
        const tempo = this.anchor ? this.anchor.tempo * .85 + measured * .15 : measured;
        const aligned = Math.abs(next - best.time) <= .65;
        this.anchor = { time: next, at: time, evidenceAt: aligned ? time : this.anchor?.evidenceAt ?? null,
          manual: !!this.anchor?.manual, tempo };
        // A nearby acoustic candidate is not evidence for the displayed bar
        // until gradual phase correction has actually brought them together.
        return this.result = this.snapshot(aligned ? 'tracking' : 'predicting', candidates);
      }
    } else this.pending = null;
    return this.result = this.snapshot(this.anchor ? 'predicting' : candidates.length ? 'candidates' : 'listening', candidates);
  }
  search(now) {
    if (now - this.frames[0].time >= 11.8) {
      const predicted = this.anchor ? this.snapshot('predicting', []).position.time : null;
      const radius = this.anchor ? Math.min(12, 1.5 + Math.max(0, now - this.anchor.at) * .25) : 12;
      return alignPhrase(this.frames, this.score, { step: STEP, predicted, radius });
    }
    const frames = this.frames.filter((f) => f.chroma && now - f.time <= 8);
    const { masks, attacks } = this.score;
    const types = [...new Set(masks)].filter((m) => m && popcount(m) < 10);
    const index = new Map(types.map((v, i) => [v, i]));
    const ids = Int16Array.from(masks, (m) => index.get(m) ?? -1);
    const dots = frames.map((f) => Float32Array.from(types, (mask) => {
      let sum = 0; for (let pc = 0; pc < 12; pc++) if (mask & 1 << pc) sum += f.chroma[pc];
      const n = popcount(mask); return sum / Math.sqrt(n - n * n / 12);
    }));
    const results = [];
    for (const speed of SPEEDS) {
      const offsets = frames.map((f) => Math.round((now - f.time) * speed / STEP));
      for (let end = offsets[0]; end < masks.length; end++) {
        if (ids[end] < 0) continue;
        let sum = 0, count = 0, recent = 0, recentN = 0, pitches = 0, transitions = 0, last = -1;
        for (let j = 0; j < offsets.length; j++) {
          const k = end - offsets[j], id = ids[k];
          if (id < 0) continue;
          sum += dots[j][id]; count++; pitches |= masks[k];
          if (now - frames[j].time <= .6) { recent += dots[j][id]; recentN++; }
          if (id !== last) transitions++;
          last = id;
        }
        if (count < offsets.length * .6 || transitions < 5 || popcount(pitches) < 3 || !recentN) continue;
        // Attacks distinguish a phrase from one sustained chord across measures.
        let n = 0; for (let k = end - offsets[0]; k <= end; k++) n += attacks[k];
        if (n < 5) continue;
        const score = sum / count * Math.sqrt(count / offsets.length);
        if (score >= .38) results.push({ time: (end + .5) * STEP, score, speed, recent: recent / recentN });
      }
    }
    return results.sort((a, b) => b.score - a.score);
  }
}
