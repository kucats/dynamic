import test from 'node:test';
import assert from 'node:assert/strict';
import { compileScore } from '../../public/reader/follow-model.mjs';
import { harmonicSalience, PartPitchMatcher, compilePartPitches, LOW_MIDI, HIGH_MIDI } from '../../tools/dynamic/following_part.mjs';

function spectrum(midi) {
  const db = new Float32Array(4096), f = 442 * 2 ** ((midi - 69) / 12), amplitudes = [.08, 1, .6, .45, .32, .25];
  for (let k = 0; k < db.length; k++) {
    let value = .00001;
    amplitudes.forEach((a, i) => { const bin = f * (i + 1) * 8192 / 48000; value += a * Math.exp(-.5 * ((k - bin) / .8) ** 2); });
    db[k] = 20 * Math.log10(value) - 20;
  }
  return db;
}
const signature = (p) => harmonicSalience(spectrum(p), 48000, 8192);
function fixture() {
  let seed = 20973;
  const melody = Array.from({ length: 400 }, () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return 50 + (seed >>> 16) % 18; });
  return { id: 'original-part-fixture', movements: [{ key: 'I', timeline: melody.map((_, i) => [i + 1, .25, 2]) }],
    notes: melody.map((p, i) => ({ mvt: 'I', id: i, bar: i + 1, off: 0, dur: .25, snd: ['', 0, p] })) };
}

test('harmonic evidence keeps register and supports a weak fundamental without selecting its louder octave', () => {
  for (const midi of [50, 55, 59, 62, 67]) {
    const f = signature(midi);
    assert.equal(f.length, HIGH_MIDI - LOW_MIDI + 1);
    assert.equal(Array.from(f).indexOf(Math.max(...f)) + LOW_MIDI, midi);
    assert.ok(f[midi - LOW_MIDI] > f[midi + 12 - LOW_MIDI]);
    assert.ok(Math.abs(f.reduce((s, v) => s + v * v, 0) - 1) < 1e-5);
  }
  assert.equal(harmonicSalience(new Float32Array(4096).fill(-40), 48000, 8192), null);
  assert.equal(harmonicSalience(new Float32Array(4096).fill(-Infinity), 48000, 8192), null);
});

test('part pitch templates exclude unresolved notes and keep octave identity', () => {
  const d = fixture(); d.notes[0].unc = 'unresolved'; d.notes[1].snd[2] = 50; d.notes[2].snd[2] = 62;
  const s = compileScore(d, 'I'), p = compilePartPitches(d, s);
  assert.equal(p.ids[0], -1);
  assert.deepEqual(p.types[p.ids[3]], [50]);
  assert.deepEqual(p.types[p.ids[5]], [62]);
});

test('a nearby-part diagnostic keeps location through original synthetic wrong, omitted and extra sounds', () => {
  const d = fixture(), s = compileScore(d, 'I'), m = new PartPitchMatcher(s, d, { tolerateErrors: true });
  const features = new Map(Array.from({ length: 20 }, (_, i) => [50 + i, signature(50 + i)]));
  let last = 0, accepted = 0, reacquired = false;
  const errors = [];
  for (let i = 0; i < 600; i++) {
    const time = i * .2, scoreTime = 10 + time, index = Math.floor(scoreTime / .5);
    let midi = d.notes[index].snd[2], f = features.get(midi);
    if (time > 25 && index % 7 === 0) f = features.get(midi + 1); // wrong semitone
    if (time > 25 && index % 11 === 0) f = null; // omitted note
    if (time > 25 && index % 13 === 0 && scoreTime % .5 < .21) f = features.get(68); // extra sound
    if (time >= 60 && time < 64) f = null;
    const r = m.push(time, f);
    if (r.position) {
      assert.ok(r.position.time >= last - 1e-7); last = r.position.time;
      if (time > 20) errors.push(Math.abs(r.position.time - scoreTime));
    }
    if (r.status === 'tracking') { accepted++; if (time > 64) reacquired = true; }
    if (time >= 60 && time < 64) assert.equal(r.status, 'predicting');
    assert.ok(m.frames.length <= 161);
  }
  errors.sort((a, b) => a - b);
  assert.ok(accepted > 250, `accepted: ${accepted}`);
  assert.ok(errors[Math.floor(errors.length * .95)] < 1, `p95 error: ${errors[Math.floor(errors.length * .95)]}`);
  assert.equal(reacquired, true);
});

test('tolerating mismatches does not turn a static wrong sound into fresh position evidence', () => {
  const d = fixture(), m = new PartPitchMatcher(compileScore(d, 'I'), d, { tolerateErrors: true });
  const f = signature(80);
  for (let i = 0; i < 300; i++) m.push(i * .2, f);
  assert.equal(m.result.position, null);
  m.override(20);
  for (let i = 300; i < 350; i++) m.push(i * .2, f);
  assert.equal(m.result.status, 'predicting');
  assert.equal(m.result.manual, true);
  assert.ok(m.result.position.time >= 29.7);
});
