import { readFileSync, writeFileSync } from 'node:fs';
import { compileScore, PhraseMatcher, profileMatchesReader, spectralChroma } from '../../public/reader/follow-model.mjs';
import { alignChroma } from '../../public/reader/follow-alignment.mjs';
import { summarizeStates } from './following_metrics.mjs';
import { harmonicSalience, PartPitchMatcher } from './following_part.mjs';
const [input, part, movement, referenceInput, windowArgument = '32', control = 'none', configuration = '{}'] = process.argv.slice(2);
const options = { template: 'ensemble', features: 'chroma', tolerateErrors: false, ...JSON.parse(configuration) };
if (!['ensemble', 'part'].includes(options.template) || !['chroma', 'harmonic'].includes(options.features) ||
    typeof options.tolerateErrors !== 'boolean' ||
    !['none', 'shuffle'].includes(control) || (options.features === 'harmonic' && options.template !== 'part') ||
    (options.tolerateErrors && options.features !== 'harmonic')) throw new Error('Invalid score diagnostic option');
if (referenceInput && (options.template !== 'ensemble' || options.features !== 'chroma' || options.tolerateErrors))
  throw new Error('Reference diagnostics do not use score-template options');
const root = new URL('../../', import.meta.url);
const reader = JSON.parse(readFileSync(new URL(`public/reader/data/${part}.json`, root)));
const profile = JSON.parse(readFileSync(new URL(`public/reader/following/${part}.json`, root)));
if (!profileMatchesReader(reader, profile)) throw new Error('Stale following profile: run tools/dynamic/build_following.py');
const score = compileScore(reader, movement, options.template === 'part' ? null : profile);
const matcher = options.features === 'harmonic' ? new PartPitchMatcher(score, reader, options) : new PhraseMatcher(score);
function shuffledIndices(length) {
  const order = Array.from({ length }, (_, i) => i); let seed = 94731;
  for (let i = order.length - 1; i > 0; i--) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    const j = seed % (i + 1); [order[i], order[j]] = [order[j], order[i]];
  }
  return order;
}
function spectra(path) {
  const bytes = readFileSync(path);
  return new Float32Array(bytes.buffer, bytes.byteOffset, bytes.length / 4);
}
function features(floats) {
  const result = [];
  for (let i = 0; i < floats.length; i += 4098) result.push({ time: floats[i], chroma:
    floats[i + 1] >= .008 ? spectralChroma(floats.subarray(i + 2, i + 4098), 48000, 8192) : null });
  return result;
}
const floats = spectra(input);
const evaluatedEnd = floats[floats.length - 4098] + 8192 / 48000 / 2;
if (referenceInput) {
  const query = features(floats), referenceFrames = features(spectra(referenceInput));
  const reference = referenceFrames.map((f) => f.chroma), windowSeconds = Number(windowArgument);
  if (![8, 16, 32].includes(windowSeconds) || !['none', 'shuffle'].includes(control)) throw new Error('Invalid diagnostic option');
  if (control === 'shuffle') {
    // Deterministic negative control: same timbres and pitch distribution, with
    // musical order destroyed. This is explicitly not the original recording.
    const shuffled = shuffledIndices(query.length).map((i) => query[i].chroma);
    query.forEach((f, i) => { f.chroma = shuffled[i]; });
  }
  const trace = [], timings = [], size = Math.round(windowSeconds / .2);
  let last = null, stable = 0;
  for (let i = size - 1; i < query.length; i += 5) {
    const q = query.slice(i - size + 1, i + 1), now = q.at(-1).time;
    const predicted = last ? last.time + last.speed : null;
    const start = performance.now(), matches = alignChroma(q, reference, { predicted, radius: 3 });
    timings.push(performance.now() - start);
    let best = matches[0];
    if (predicted != null) best = matches.find((c) => Math.abs(c.time - predicted) < 3 && c.score >= (best?.score || 0) - .06) || best;
    const margin = best ? best.score - (matches.find((c) => Math.abs(c.time - best.time) > 3)?.score || 0) : 0;
    const supported = best && best.score > .4 && best.recent > .25;
    const consistent = last && best && best.time - last.time > .2 && best.time - last.time < 2.3;
    stable = supported && consistent && (stable > 0 || margin > .035) ? stable + 1 : supported && margin > .035 ? 1 : 0;
    trace.push({ audio: now, reference: best ? best.time - .1 + referenceFrames[0].time : null,
      status: stable >= 3 ? 'tracking_candidate' : 'uncertain', score: best?.score ?? null, margin,
      score_position: null, confirmed: false });
    last = supported ? best : null;
  }
  timings.sort((a, b) => a - b);
  writeFileSync(1, JSON.stringify({ algorithm: 'local-context-dtw-reference-diagnostic-v2', window_seconds: windowSeconds,
    control, evidence_kind: 'reference_audio_alignment_not_ground_truth', score_position: null,
    ...summarizeStates(trace, 1, evaluatedEnd), processing_ms: { p50: timings[Math.floor(timings.length * .5)],
      p95: timings[Math.floor(timings.length * .95)], max: timings.at(-1) }, trace }) + '\n');
  process.exit(0);
}
const counts = {}, trace = [], states = [], timings = [];
const order = control === 'shuffle' ? shuffledIndices(floats.length / 4098) : null;
let frames = 0, rewinds = 0, previous = null;
for (let i = 0; i < floats.length; i += 4098) {
  const featureOffset = order ? order[i / 4098] * 4098 : i;
  const time = floats[i], rms = floats[featureOffset + 1], db = floats.subarray(featureOffset + 2, featureOffset + 4098);
  const start = performance.now();
  const extract = options.features === 'harmonic' ? harmonicSalience : spectralChroma;
  const result = matcher.push(time, rms >= .008 ? extract(db, 48000, 8192) : null);
  timings.push(performance.now() - start);
  frames++; counts[result.status] = (counts[result.status] || 0) + 1;
  states.push({ audio: time, status: result.status });
  if (previous && result.position && result.position.time < previous.time - .01) rewinds++;
  previous = result.position;
  if (frames % 5 === 0) trace.push({ audio: +time.toFixed(3), status: result.status,
    bar: result.position?.bar ?? null, occurrence: result.position?.occurrence ?? null,
    tempo: result.tempo, candidates: result.candidates.map((c) => ({ bar: c.bar, score: +c.score.toFixed(3) })) });
}
timings.sort((a, b) => a - b);
console.log(JSON.stringify({ algorithm: options.features === 'harmonic' ? 'part-harmonic-diagnostic-v1' : 'local-ensemble-context-dtw-v2',
  part, movement, ...options, control, frames, counts, rewinds,
  ...summarizeStates(states, .2, evaluatedEnd),
  processing_ms: { p50: timings[Math.floor(timings.length * .5)], p95: timings[Math.floor(timings.length * .95)], max: timings.at(-1) }, trace }));
