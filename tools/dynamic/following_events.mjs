// Offline experiment. Event hypotheses are not isolated trombone notes or
// verified performance errors. The reader does not load this module.
import { PhraseMatcher } from '../../public/reader/follow-model.mjs';
import { LOW_MIDI } from './following_part.mjs';

const MAX_EVENTS = 24;
const SPEEDS = [.5, .65, .8, 1, 1.25, 1.6, 2];
const GAP_COST = .85;

export function compilePartEvents(reader, score) {
  const byBar = new Map();
  for (const n of reader.notes) {
    if (n.mvt !== score.movement || n.unc || n.dur <= 0 || !Number.isFinite(n.snd?.[2])) continue;
    if (!byBar.has(n.bar)) byBar.set(n.bar, []);
    byBar.get(n.bar).push(n);
  }
  const events = [];
  for (const b of score.bars) {
    for (const n of (byBar.get(b.bar) || []).slice().sort((a, c) => a.off - c.off)) {
      const time = b.start + n.off * b.seconds;
      const end = Math.min(b.end, b.start + (n.off + n.dur) * b.seconds);
      if (time >= end) continue;
      const last = events.at(-1), pitch = n.snd[2];
      if (n.tie) {
        // Orphan/unresolved tie continuations never become invented attacks.
        if (last && last.pitches.length === 1 && last.pitches[0] === pitch && Math.abs(last.end - time) < .001)
          last.end = end;
        continue;
      }
      if (last && Math.abs(last.time - time) < .001) {
        if (!last.pitches.includes(pitch)) last.pitches.push(pitch);
        last.end = Math.max(last.end, end);
      } else events.push({ time, end, pitches: [pitch], bar: b.bar, occurrence: b.occurrence });
    }
  }
  return events;
}

// Two consecutive frames confirm a pitch-region change. The full feature
// vector survives; the region is only a segmentation hint. A repeated pitch
// without a detectable break is one event (a known 200 ms frontend limitation).
export function extractEvents(frames) {
  const events = [];
  let active = null, pending = null, previousTime = -Infinity;
  for (const f of frames) {
    if (f.time - previousTime > .65) { active = null; pending = null; }
    previousTime = f.time;
    const peak = f.chroma && Math.max(...f.chroma);
    if (!f.chroma || peak < .2) { active = null; pending = null; continue; }
    const pitch = f.chroma.indexOf(peak);
    if (active?.pitch === pitch) {
      active.end = f.time; active.count++;
      for (let k = 0; k < f.chroma.length; k++) active.sum[k] += f.chroma[k];
      pending = null;
    } else {
      if (pending?.pitch !== pitch) pending = { time: f.time, end: f.time, pitch, count: 1, sum: Float64Array.from(f.chroma) };
      else {
        pending.end = f.time; pending.count++;
        for (let k = 0; k < f.chroma.length; k++) pending.sum[k] += f.chroma[k];
        active = pending; pending = null; events.push(active);
      }
    }
  }
  return events.map((e) => ({ time: e.time, end: e.end, pitch: e.pitch + LOW_MIDI,
    feature: Float32Array.from(e.sum, (v) => v / e.count) }));
}

function support(observation, expected) {
  const peak = Math.max(...observation.feature);
  return Math.max(0, Math.min(1, Math.max(...expected.pitches.map((p) =>
    (observation.feature[p - LOW_MIDI] || 0) / Math.max(.001, peak)))));
}

// Subsequence edit alignment with explicit substitution, observation insertion
// and score deletion costs. IOIs span skipped events on BOTH sides; an extra
// sound cannot reset the clock and collapse an intervening rest.
export function alignEvents(observations, reference, now, diagnostic = {}) {
  const query = observations.slice(-MAX_EVENTS);
  const n = query.length, m = reference.length;
  diagnostic.observations = n; diagnostic.eligible = false; diagnostic.bestRawQuality = null;
  if (n < 8 || !m || now - query.at(-1).end > .6 || now - query.at(-1).time > 1.2 ||
      query.at(-1).time - query[0].time < 4 || new Set(query.map((e) => e.pitch)).size < 4) return [];
  diagnostic.eligible = true;
  const similarities = query.map((q) => Float32Array.from(reference, (r) => support(q, r)));
  const candidates = [];
  for (const speed of SPEEDS) {
    const costs = new Float64Array(n * m).fill(Infinity);
    const previous = new Int32Array(n * m).fill(-1);
    for (let i = 0; i < n; i++) for (let j = 0; j < m; j++) {
      const index = i * m + j, pitchCost = 1 - similarities[i][j];
      // At most two leading observations may be unexplained insertions.
      if (i <= 2) costs[index] = i * GAP_COST + pitchCost;
      for (let di = 1; di <= Math.min(3, i); di++) for (let dj = 1; dj <= Math.min(3, j); dj++) {
        const prevIndex = (i - di) * m + j - dj;
        if (!Number.isFinite(costs[prevIndex])) continue;
        const elapsed = query[i].time - query[i - di].time;
        const distance = reference[j].time - reference[j - dj].time;
        const ratio = distance / elapsed;
        if (elapsed <= 0 || distance <= 0 || ratio < .35 || ratio > 2.8) continue;
        const rhythmCost = .45 * Math.min(2, Math.abs(Math.log2(ratio / speed)));
        const cost = costs[prevIndex] + pitchCost + rhythmCost + (di + dj - 2) * GAP_COST;
        if (cost < costs[index]) { costs[index] = cost; previous[index] = prevIndex; }
      }
    }
    for (let j = 0; j < m; j++) {
      let index = (n - 1) * m + j;
      const quality = 1 - costs[index] / n;
      if (Number.isFinite(quality)) diagnostic.bestRawQuality = Math.max(diagnostic.bestRawQuality ?? -Infinity, quality);
      if (quality < .68 || similarities[n - 1][j] < .7) continue;
      const path = [];
      while (index >= 0) { path.push([Math.floor(index / m), index % m]); index = previous[index]; }
      path.reverse();
      const good = path.filter(([a, b]) => similarities[a][b] >= .7);
      const deletions = path.reduce((sum, p, k) => sum + (k ? p[1] - path[k - 1][1] - 1 : 0), 0);
      const insertions = n - path.length, substitutions = path.length - good.length;
      if (good.length < 6 || good.length / n < .65 || new Set(good.map(([, b]) => reference[b].pitches.join(','))).size < 4) continue;
      const intervals = path.slice(1).map(([a, b], k) =>
        (reference[b].time - reference[path[k][1]].time) / (query[a].time - query[path[k][0]].time));
      const recentSpeeds = intervals.slice(-5).sort((a, b) => a - b);
      const measured = recentSpeeds[Math.floor(recentSpeeds.length / 2)] || speed;
      const last = reference[j], time = last.time + (now - query.at(-1).time) * measured;
      // Do not extrapolate stale event matches past the end of the played note.
      if (time > last.end + .25) continue;
      candidates.push({ time, score: quality, speed: measured, recent: similarities[n - 1][j],
        context: now - query[0].time, method: 'event-sequence',
        evidence: { matched: good.length, substitutions, insertions, deletions, observations: n } });
    }
  }
  const separated = [];
  for (const c of candidates.sort((a, b) => b.score - a.score))
    if (separated.every((p) => Math.abs(p.time - c.time) > 1)) separated.push(c);
  return separated;
}

export class EventSequenceMatcher extends PhraseMatcher {
  constructor(score, reader) {
    super(score); this.events = compilePartEvents(reader, score);
    this.diagnostic = { searches: 0, eligibleSearches: 0, maxObservations: 0, bestRawQuality: null, candidateSearches: 0 };
  }
  search(now) {
    this.lastEvents = extractEvents(this.frames);
    const stats = {};
    this.lastMatches = alignEvents(this.lastEvents, this.events, now, stats);
    this.diagnostic.searches++;
    if (stats.eligible) this.diagnostic.eligibleSearches++;
    this.diagnostic.maxObservations = Math.max(this.diagnostic.maxObservations, stats.observations);
    if (stats.bestRawQuality != null)
      this.diagnostic.bestRawQuality = Math.max(this.diagnostic.bestRawQuality ?? -Infinity, stats.bestRawQuality);
    if (this.lastMatches.length) this.diagnostic.candidateSearches++;
    return this.lastMatches;
  }
}
