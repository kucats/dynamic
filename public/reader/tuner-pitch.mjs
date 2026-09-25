/* DYNAMIC tuner — pitch detection and note naming (pure functions, no DOM or audio). */

// YIN (de Cheveigné & Kawahara 2002) on a mono buffer. Signals at 44.1/48 kHz are halved first:
// brass fundamentals sit well under 1.4 kHz, and the difference function costs O(n·τ).
export function detectPitch(input, sampleRate, { minHz = 50, maxHz = 1400, threshold = 0.12, minRms = 0.01 } = {}) {
  let buf = input, sr = sampleRate;
  if (sr >= 32000) {
    const half = new Float32Array(buf.length >> 1);
    for (let i = 0; i < half.length; i++) half[i] = (buf[2 * i] + buf[2 * i + 1]) / 2;
    buf = half; sr /= 2;
  }
  let sum = 0, mean = 0;
  for (let i = 0; i < buf.length; i++) mean += buf[i];
  mean /= buf.length;
  for (let i = 0; i < buf.length; i++) sum += (buf[i] - mean) ** 2;
  const rms = Math.sqrt(sum / buf.length);
  if (rms < minRms) return { freq: null, clarity: 0, rms };
  const tauMin = Math.max(2, Math.floor(sr / maxHz)), tauMax = Math.min(Math.floor(sr / minHz), Math.floor(buf.length / 2));
  const W = buf.length - tauMax, d = new Float32Array(tauMax + 2);
  for (let tau = 1; tau <= tauMax + 1 && tau + W <= buf.length; tau++) {
    let s = 0;
    for (let i = 0; i < W; i++) { const x = buf[i] - buf[i + tau]; s += x * x; }
    d[tau] = s;
  }
  // cumulative mean normalised difference
  const c = new Float32Array(tauMax + 2); c[0] = 1;
  let run = 0;
  for (let tau = 1; tau <= tauMax + 1; tau++) { run += d[tau]; c[tau] = run ? (d[tau] * tau) / run : 1; }
  let tau = -1;
  for (let t = tauMin; t <= tauMax; t++) {
    if (c[t] < threshold) { while (t + 1 <= tauMax && c[t + 1] < c[t]) t++; tau = t; break; }
  }
  if (tau < 0) {                                   // no clear dip: accept the best one only if it is fairly clean
    let best = tauMin;
    for (let t = tauMin; t <= tauMax; t++) if (c[t] < c[best]) best = t;
    if (c[best] > 0.3) return { freq: null, clarity: 1 - c[best], rms };
    tau = best;
  }
  // parabolic refinement on the raw difference, which is smoother than the normalised curve
  const a = d[tau - 1], b = d[tau], e = tau + 1 <= tauMax ? d[tau + 1] : b, den = a - 2 * b + e;
  const shift = den > 0 ? Math.max(-0.5, Math.min(0.5, (a - e) / (2 * den))) : 0;
  return { freq: sr / (tau + shift), clarity: Math.max(0, 1 - c[tau]), rms };
}

export function noteOf(freq, a4 = 442) {
  const m = 69 + 12 * Math.log2(freq / a4), midi = Math.round(m);
  return { midi, cents: (m - midi) * 100 };
}

const EN = ['C', 'C♯', 'D', 'E♭', 'E', 'F', 'F♯', 'G', 'A♭', 'A', 'B♭', 'B'];
const DE = ['C', 'C♯', 'D', 'E♭', 'E', 'F', 'F♯', 'G', 'A♭', 'A', 'B♭', 'H'];   // as in the trombone reader parts (H = B natural)
const SOL = ['ド', 'ド♯', 'レ', 'ミ♭', 'ミ', 'ファ', 'ファ♯', 'ソ', 'ラ♭', 'ラ', 'シ♭', 'シ'];
const pc = (m) => ((m % 12) + 12) % 12;

// Names for a MIDI note in the reader's convention: trombone parts use German letters, horn parts
// fixed ドレミ. `written` (horn only) is the F-horn reading, a fifth above the sounding pitch.
export function nameOf(midi, instrument = 'horn', { written = false } = {}) {
  const m = instrument === 'horn' && written ? midi + 7 : midi;
  const octave = Math.floor(m / 12) - 1;
  return { main: instrument === 'trombone' ? DE[pc(m)] : SOL[pc(m)], sub: EN[pc(m)], octave, midi: m };
}
