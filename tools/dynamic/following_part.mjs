// Local diagnostic only: register-aware evidence for a nearby brass part.
// Not source separation, not a trained timbre classifier, not enabled in reader.
import { PhraseMatcher, STEP } from '../../public/reader/follow-model.mjs';
import { alignEvidence } from '../../public/reader/follow-alignment.mjs';

export const LOW_MIDI = 36, HIGH_MIDI = 84;
const SIZE = HIGH_MIDI - LOW_MIDI + 1;

function prominence(db, frequency, sampleRate, fftSize) {
  const bin = frequency * fftSize / sampleRate;
  const a = Math.max(1, Math.floor(bin * .977)), b = Math.min(db.length - 1, Math.ceil(bin * 1.023));
  if (a >= db.length - 1) return 0;
  let peak = -140;
  for (let i = a; i <= b; i++) peak = Math.max(peak, Number.isFinite(db[i]) ? db[i] : -140);
  const l = Math.max(1, Math.floor(bin * .9)), r = Math.min(db.length - 1, Math.ceil(bin * 1.1));
  let floor = 0, count = 0;
  for (let i = l; i <= r; i++) if (i < a || i > b) { floor += Number.isFinite(db[i]) ? db[i] : -140; count++; }
  return Math.max(0, Math.min(24, peak - floor / Math.max(1, count) - 4)) * Math.max(0, Math.min(1, (peak + 85) / 35));
}

export function harmonicSalience(db, sampleRate, fftSize, a4 = 442) {
  const values = new Float32Array(SIZE);
  for (let midi = LOW_MIDI; midi <= HIGH_MIDI; midi++) {
    const hz = a4 * 2 ** ((midi - 69) / 12);
    // Keep multiple hypotheses. Higher harmonics support a weak fundamental;
    // no loudest spectral peak is declared to be the trombone's played note.
    let weighted = 0, weight = 0, supported = 0;
    for (let h = 1; h <= 6; h++) {
      if (hz * h > Math.min(8000, sampleRate / 2)) break;
      const v = prominence(db, hz * h, sampleRate, fftSize), w = 1 / Math.sqrt(h);
      weighted += w * v; weight += w;
      if (v > 3) supported++;
    }
    values[midi - LOW_MIDI] = weighted / Math.max(.01, weight) * Math.min(1, supported / 3);
  }
  const mean = values.reduce((sum, v) => sum + v, 0) / SIZE;
  let norm = 0;
  for (let i = 0; i < SIZE; i++) { values[i] -= mean; norm += values[i] ** 2; }
  if (norm < 10) return null;
  return Float32Array.from(values, (v) => v / Math.sqrt(norm));
}

export function compilePartPitches(reader, score) {
  const notes = new Map();
  for (const n of reader.notes) {
    if (n.mvt !== score.movement || n.unc || n.dur <= 0 || !Number.isFinite(n.snd[2])) continue;
    if (!notes.has(n.bar)) notes.set(n.bar, []);
    notes.get(n.bar).push(n);
  }
  const rows = Array.from({ length: score.masks.length }, () => new Set());
  for (const b of score.bars) for (const n of notes.get(b.bar) || []) {
    const midi = n.snd[2];
    if (midi < LOW_MIDI || midi > HIGH_MIDI) continue;
    const start = b.start + n.off * b.seconds, end = Math.min(b.end, b.start + (n.off + n.dur) * b.seconds);
    for (let i = Math.max(0, Math.ceil(start / STEP - .5)); i < rows.length && (i + .5) * STEP < end; i++) rows[i].add(midi);
  }
  const types = [], byKey = new Map(), ids = new Int32Array(rows.length).fill(-1);
  for (let i = 0; i < rows.length; i++) {
    if (!rows[i].size) continue;
    const pitches = [...rows[i]].sort((a, b) => a - b), key = pitches.join(',');
    if (!byKey.has(key)) { byKey.set(key, types.length); types.push(pitches); }
    ids[i] = byKey.get(key);
  }
  return { types, ids };
}

export class PartPitchMatcher extends PhraseMatcher {
  constructor(score, reader, { tolerateErrors = false } = {}) {
    super(score); this.pitchTemplate = compilePartPitches(reader, score); this.tolerateErrors = tolerateErrors;
  }
  search(now) {
    if (now - this.frames[0].time < 11.8) return [];
    const { types, ids } = this.pitchTemplate;
    const dots = this.frames.map((f) => Float32Array.from(types, (pitches) => {
      if (!f.chroma) return 0;
      const sum = pitches.reduce((value, p) => value + f.chroma[p - LOW_MIDI], 0), n = pitches.length;
      return sum / Math.sqrt(n - n * n / SIZE);
    }));
    const predicted = this.anchor ? this.snapshot('predicting', []).position.time : null;
    const radius = this.anchor ? Math.min(12, 1.5 + Math.max(0, now - this.anchor.at) * .25) : 12;
    return alignEvidence(this.frames, dots, ids, this.score.masks, { step: STEP, predicted, radius,
      outlierFloor: this.tolerateErrors ? 0 : -1 });
  }
}
