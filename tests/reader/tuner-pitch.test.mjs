import test from 'node:test';
import assert from 'node:assert/strict';
import { detectPitch, noteOf, nameOf } from '../../public/reader/tuner-pitch.mjs';

const SR = 48000;
function tone(freq, { n = 4096, harmonics = [1], noise = 0, seed = 1 } = {}) {
  const b = new Float32Array(n); let s = seed;
  const rnd = () => { s = (s * 16807) % 2147483647; return s / 2147483647 - 0.5; };
  for (let i = 0; i < n; i++) {
    let v = 0; harmonics.forEach((a, h) => { v += a * Math.sin(2 * Math.PI * freq * (h + 1) * i / SR + h); });
    b[i] = 0.3 * v + noise * rnd();
  }
  return b;
}
const cents = (f, ref) => 1200 * Math.log2(f / ref);

test('pure tones across the horn and trombone range within 1 cent', () => {
  for (const f of [58.27, 87.31, 116.54, 233.08, 349.23, 442, 698.46, 1046.5]) {
    const r = detectPitch(tone(f), SR);
    assert.ok(r.freq, `detected ${f}`);
    assert.ok(Math.abs(cents(r.freq, f)) < 1, `${f} Hz → ${r.freq}`);
  }
});

test('brass-like spectrum with a weak fundamental is not read an octave off', () => {
  for (const f of [65.41, 110, 174.61, 293.66]) {
    const r = detectPitch(tone(f, { harmonics: [0.25, 1, 0.8, 0.6, 0.45, 0.3, 0.2], noise: 0.05 }), SR);
    assert.ok(r.freq && Math.abs(cents(r.freq, f)) < 3, `${f} Hz → ${r.freq}`);
  }
});

test('silence and noise give no pitch', () => {
  assert.equal(detectPitch(new Float32Array(4096), SR).freq, null);
  assert.equal(detectPitch(tone(440, { harmonics: [0], noise: 0.8 }), SR).freq, null);
});

test('44.1 kHz and odd rates work too', () => {
  const b = new Float32Array(4096);
  for (let i = 0; i < b.length; i++) b[i] = 0.3 * Math.sin(2 * Math.PI * 329.63 * i / 44100);
  assert.ok(Math.abs(cents(detectPitch(b, 44100).freq, 329.63)) < 1);
  const c = new Float32Array(2048);
  for (let i = 0; i < c.length; i++) c[i] = 0.3 * Math.sin(2 * Math.PI * 196 * i / 22050);
  assert.ok(Math.abs(cents(detectPitch(c, 22050).freq, 196)) < 1);
});

test('note and cents follow the chosen A4', () => {
  assert.deepEqual(noteOf(442, 442), { midi: 69, cents: 0 });
  const r = noteOf(440, 442); assert.equal(r.midi, 69); assert.ok(Math.abs(r.cents + 7.85) < 0.05);
  const s = noteOf(466.16 * 442 / 440 * 2 ** (20 / 1200), 442); assert.equal(s.midi, 70); assert.ok(Math.abs(s.cents - 20) < 0.1);
});

test('names follow the reader: German letters for trombone, fixed ドレミ for horn, F reading a fifth up', () => {
  assert.deepEqual(nameOf(58, 'trombone'), { main: 'B♭', sub: 'B♭', octave: 3, midi: 58 });
  assert.equal(nameOf(59, 'trombone').main, 'H');
  assert.equal(nameOf(62, 'horn').main, 'レ');
  const w = nameOf(62, 'horn', { written: true }); assert.equal(w.main, 'ラ'); assert.equal(w.octave, 4);
  assert.equal(nameOf(62, 'trombone', { written: true }).main, 'D', 'no F reading for trombone');
  assert.equal(nameOf(60, 'horn').octave, 4);
});
