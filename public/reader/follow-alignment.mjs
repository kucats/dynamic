// Bounded, causal subsequence DTW. Missing score voices carry no evidence.
// Similarity is a ranking heuristic, never a calibrated probability.
const countBits = (n) => { let k = 0; for (; n; n &= n - 1) k++; return k; };
const cache = new WeakMap();

function prepare(score) {
  if (cache.has(score)) return cache.get(score);
  const types = [...new Set(score.masks)].filter((m) => m && countBits(m) < 10);
  const index = new Map(types.map((m, i) => [m, i]));
  const result = { types, ids: Int16Array.from(score.masks, (m) => index.get(m) ?? -1),
    norms: Float32Array.from(types, (m) => { const n = countBits(m); return Math.sqrt(n - n * n / 12); }) };
  cache.set(score, result); return result;
}

export function alignPhrase(frames, score, options = {}) {
  const { types, ids, norms } = prepare(score);
  const dots = frames.map((f) => Float32Array.from(types, (mask, index) => {
    if (!f.chroma) return 0;
    let sum = 0; for (let k = 0; k < 12; k++) if (mask & 1 << k) sum += f.chroma[k];
    return sum / norms[index];
  }));
  return alignEvidence(frames, dots, ids, score.masks, options);
}

// Diagnostic audio-to-audio comparison uses the SAME alignment recurrence.
// Returned seconds belong to that reference audio; they are never bar labels.
export function alignChroma(frames, reference, options = {}) {
  if (frames.length * reference.length > 4_000_000) return [];
  const ids = Int32Array.from(reference, (r, j) => r ? j : -1);
  const masks = Uint16Array.from(reference, (r) => r ? r.reduce((m, v, k) => v > .15 ? m | 1 << k : m, 0) : 0);
  const dots = frames.map((f) => Float32Array.from(reference, (r) => {
    if (!r || !f.chroma) return 0;
    let sum = 0; for (let k = 0; k < 12; k++) sum += f.chroma[k] * r[k];
    return sum;
  }));
  return alignEvidence(frames, dots, ids, masks, options);
}

// Shared recurrence for offline feature experiments. outlierFloor=0 treats a
// contradicting observation as missing evidence, never as a positive match.
// The reader keeps the original -1 floor until labelled evaluation supports a
// change. Fresh-support gating below always uses the unmodified similarities.
export function alignEvidence(frames, dots, ids, masks, { step = .2, predicted = null, radius = 12, outlierFloor = -1 } = {}) {
  const n = frames.length, m = ids.length;
  if (n < 2 || n * m > 4_000_000) return [];
  // (1,1), (1,2), (2,1) permit local tempo changes between half and double
  // speed. Small warp cost discourages explaining noise with extreme timing.
  const back = new Uint8Array(n * m), width = m + 2;
  let previous2 = new Float32Array(width).fill(Infinity), previous = new Float32Array(width);
  let previousCost = new Float32Array(m).fill(1);
  for (let i = 0; i < n; i++) {
    const row = new Float32Array(width).fill(Infinity), cost = new Float32Array(m);
    for (let j = 0; j < m; j++) cost[j] = 1 - (ids[j] < 0 ? 0 : Math.max(outlierFloor, dots[i][ids[j]]));
    for (let j = 0; j < m; j++) {
      let best = previous[j + 1] + 2 * cost[j], direction = 1;
      if (j > 0) {
        const fast = previous[j] + cost[j - 1] + cost[j] + .035;
        if (fast < best) { best = fast; direction = 2; }
      }
      if (i > 0) {
        // This step consumes TWO query frames. Count both with the same
        // per-query weight as diagonal steps; otherwise slow paths win even
        // on unrelated audio merely by accumulating half as much cost.
        const slow = previous2[j + 1] + 2 * previousCost[j] + 2 * cost[j] + .035;
        if (slow < best) { best = slow; direction = 3; }
      }
      row[j + 2] = best; back[i * m + j] = direction;
    }
    previous2 = previous; previous = row; previousCost = cost;
  }
  const ranked = Array.from({ length: m }, (_, j) => j).sort((a, b) => previous[a + 2] - previous[b + 2]);
  const ends = [];
  for (const end of ranked) {
    if (ends.every((j) => Math.abs(j - end) * step > 2.4)) ends.push(end);
    if (ends.length === 8) break;
  }
  // A distant motif must not hide a viable continuation of the chosen path.
  if (predicted != null) {
    const local = ranked.find((j) => Math.abs((j + .5) * step - predicted) <= radius);
    if (local != null && !ends.includes(local)) ends.push(local);
  }
  const results = [];
  for (const end of ends) {
    let i = n - 1, j = end;
    const mapped = new Float32Array(n).fill(-1);
    while (i >= 0 && j >= 0) {
      mapped[i] = j;
      const direction = back[i * m + j];
      if (direction === 3) { if (i > 0) mapped[i - 1] = j; i -= 2; j--; }
      else if (direction === 2) { i--; j -= 2; }
      else { i--; j--; }
    }
    if (i >= 0) continue;
    let evidence = 0, voiced = 0, recent = 0, recentN = 0, transitions = 0, pitches = 0, last = -1;
    const now = frames[n - 1].time;
    let sx = 0, sy = 0, sxx = 0, sxy = 0, points = 0;
    for (let k = 0; k < n; k++) {
      const ref = mapped[k], age = now - frames[k].time;
      if (ref < 0) continue;
      if (age <= 6) { const x = -age, y = ref * step; sx += x; sy += y; sxx += x * x; sxy += x * y; points++; }
      if (!frames[k].chroma) continue;
      voiced++;
      const id = ids[ref];
      if (id < 0) continue;
      evidence++; pitches |= masks[ref];
      if (masks[ref] !== last) transitions++;
      last = masks[ref];
      if (age <= 1.2) { recent += dots[k][id]; recentN++; }
    }
    const context = now - frames[0].time;
    const denominator = points * sxx - sx * sx;
    const speed = denominator > .01 ? (points * sxy - sx * sy) / denominator : 1;
    // A path through an absent part, a pedal tone or a mostly silent input is
    // not a phrase. Retained history cannot manufacture fresh evidence.
    if (voiced < n * .6 || evidence < n * .35 || evidence * step < 4 || transitions < (context >= 12 ? 8 : 5) || countBits(pitches) < 4) continue;
    results.push({ time: (end + .5) * step, score: 1 - previous[end + 2] / (2 * n),
      speed: Math.max(.5, Math.min(2, speed)), recent: recentN >= 3 ? recent / recentN : 0,
      context, coverage: evidence / n, method: 'context-dtw' });
  }
  return results.sort((a, b) => b.score - a.score);
}
