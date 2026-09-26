import test from 'node:test';
import assert from 'node:assert/strict';
import { compileScore, locate, PhraseMatcher, positionLabel, profileMatchesReader, spectralChroma } from '../../public/reader/follow-model.mjs';
import { readFileSync } from 'node:fs';
import { alignPhrase, alignChroma } from '../../public/reader/follow-alignment.mjs';
import { summarizeStates } from '../../tools/dynamic/following_metrics.mjs';

// Original artificial phrase; these checks are not real-recording accuracy.
const pitches = [60, 64, 67, 62, 65, 69, 61, 68, 63, 66, 70, 62, 65, 60, 67, 64];
const feature = (p) => Float32Array.from({ length: 12 }, (_, k) => (k === p % 12 ? 11 : -1) / Math.sqrt(132));
function fixture(repeat = false) {
  const timeline = pitches.map((_, i) => [i + 1, .25, 2]);
  return { id: 'original-fixture', movements: [{ key: 'I', timeline: repeat ? [...timeline, ...timeline] : timeline }],
    notes: pitches.map((p, i) => ({ id: i + 1, mvt: 'I', bar: i + 1, off: 0, dur: .25, snd: ['', 0, p], w: ['', 0, p + 7] })) };
}
function perform(matcher, duration = 7.8) {
  for (let i = 0; i * .2 < duration; i++) matcher.push(i * .2, feature(pitches[Math.floor(i * .2 / .5) % pitches.length]));
  return matcher.result;
}

test('concert pitch, uncertain masks, full rests and repeat occurrences', () => {
  const d = fixture(true); d.notes[0].unc = 'unresolved';
  const s = compileScore(d, 'I');
  assert.equal(s.duration, 16);
  assert.equal(s.masks[0], 0);
  assert.equal(s.masks[3], 1 << 4); // E concert, never written B
  assert.equal(locate(s, 8.1).occurrence, 2);
  assert.match(positionLabel(s, locate(s, 8.1)), /2回目/);
});

test('a continuing distinctive phrase acquires the right measure', () => {
  const m = new PhraseMatcher(compileScore(fixture(), 'I'));
  const r = perform(m);
  assert.equal(r.status, 'tracking');
  assert.equal(r.position.bar, 16);
  assert.ok(Math.abs(r.position.time - 7.6) < .3);
});

test('identical repeat occurrences remain alternatives until the user chooses', () => {
  const s = compileScore(fixture(true), 'I'), m = new PhraseMatcher(s);
  const r = perform(m);
  assert.equal(r.position, null);
  assert.ok(r.candidates.some((c) => c.occurrence === 1));
  assert.ok(r.candidates.some((c) => c.occurrence === 2));
  m.override(8); m.hold();
  const chosen = perform(m);
  assert.equal(chosen.manual, true);
  assert.equal(chosen.position.occurrence, 2);
  assert.equal(chosen.position.bar, 16);
});

test('losing sound continues at the last BPM, including through a nominal tempo change', () => {
  const d = fixture(); d.movements[0].timeline[2][2] = 4; // score marks half tempo here
  const s = compileScore(d, 'I'), m = new PhraseMatcher(s);
  m.override(0);
  m.push(0, null); const r = m.push(1.6, null);
  assert.equal(r.status, 'predicting');
  assert.equal(r.tempo, 120);
  assert.equal(r.position.bar, 4); // constant 120 BPM, NOT the changed score tempo
  assert.ok(r.uncertainty > .4);
});

test('stop freezes; a fresh AudioContext clock can resume from zero', () => {
  const m = new PhraseMatcher(compileScore(fixture(true), 'I'));
  m.override(1); m.push(100, null); m.push(102, null);
  const stopped = m.hold().position.time;
  m.push(.2, null); const r = m.push(1.2, null);
  assert.ok(Math.abs(r.position.time - stopped - 1) < .001);
  assert.equal(r.manual, true);
});

test('manual override replaces old history and distant high scores cannot relocate it', () => {
  const d = fixture(true); d.movements[0].timeline = [...d.movements[0].timeline, ...d.movements[0].timeline];
  const m = new PhraseMatcher(compileScore(d, 'I'));
  m.override(20, 0);
  // Deliberately hostile high-scoring competing paths outside the local corridor.
  m.search = () => [{ time: 1, score: .99, recent: 1, speed: 1 }];
  const r = perform(m, 6);
  assert.equal(r.manual, true);
  assert.equal(r.status, 'predicting');
  assert.ok(r.position.time >= 25.7);
  m.override(3);
  assert.equal(m.result.position.time, 3);
  assert.equal(m.frames.length, 0);
  m.reset(); assert.equal(m.result.position, null);
});

test('phase recovery never moves the cursor backwards', () => {
  const m = new PhraseMatcher(compileScore(fixture(true), 'I'));
  m.override(0, 0);
  m.search = (now) => [{ time: Math.max(0, now - .8), score: .9, recent: .9, speed: .9 }];
  let last = 0;
  for (let i = 0; i < 60; i++) {
    const r = m.push(i * .2, feature(pitches[Math.floor(i * .2 / .5) % pitches.length]));
    assert.ok(r.position.time >= last - 1e-6);
    assert.ok(r.position.time - last < .6);
    last = r.position.time;
  }
});

test('silence, flat noise and a static tone cannot identify a phrase', () => {
  assert.equal(spectralChroma(new Float32Array(4096).fill(-Infinity), 48000, 8192), null);
  assert.equal(spectralChroma(new Float32Array(4096).fill(-50), 48000, 8192), null);
  const m = new PhraseMatcher(compileScore(fixture(), 'I'));
  for (let i = 0; i < 70; i++) m.push(i * .2, feature(60));
  assert.equal(m.result.position, null);
  assert.equal(m.result.candidates.length, 0);
});

test('short breaths retain phrase history; a three-note mixture can be followed', () => {
  const m = new PhraseMatcher(compileScore(fixture(), 'I'));
  for (let i = 0; i < 39; i++) {
    const pc = pitches[Math.floor(i * .2 / .5)] % 12;
    const pcs = [pc, (pc + 4) % 12, (pc + 7) % 12];
    const chord = Float32Array.from({ length: 12 }, (_, k) => ((pcs.includes(k) ? 1 : 0) - .25) / 1.5);
    m.push(i * .2, i % 9 === 8 ? null : chord);
  }
  assert.ok(m.result.position);
  assert.ok(m.result.position.bar >= 15);
});

test('worker fences stale audio after a manual command and old movements', async () => {
  const previous = globalThis.self, messages = [];
  globalThis.self = { postMessage: (value) => messages.push(value) };
  try {
    await import('../../public/reader/follow-worker.mjs');
    const send = (d) => self.onmessage({ data: d });
    send({ type: 'init', generation: 1, revision: 0, reader: fixture(), movement: 'I' });
    send({ type: 'override', generation: 1, revision: 2, time: 3 });
    send({ type: 'frame', generation: 1, revision: 1, time: 50, chroma: feature(60) });
    assert.equal(messages.length, 1);
    assert.equal(messages[0].result.position.time, 3);
    assert.equal(messages[0].revision, 2);
    send({ type: 'init', generation: 2, revision: 0, reader: fixture(), movement: 'I' });
    send({ type: 'override', generation: 1, revision: 99, time: 7 });
    assert.equal(messages.length, 1);
    send({ type: 'frame', generation: 2, revision: 0, time: 1, chroma: null });
    assert.equal(messages.at(-1).result.position, null);
  } finally {
    if (previous === undefined) delete globalThis.self; else globalThis.self = previous;
  }
});

function longFixture(length = 320) {
  let seed = 734921;
  const melody = Array.from({ length }, () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return 60 + (seed >>> 16) % 12; });
  const data = { id: 'original-long-fixture', movements: [{ key: 'I', timeline: melody.map((_, i) => [i + 1, .25, 4]) }],
    notes: melody.map((p, i) => ({ id: i + 1, mvt: 'I', bar: i + 1, off: 0, dur: .25, snd: ['', 0, p] })) };
  return { melody, data };
}

test('32 seconds of context distinguish motifs whose last 8 seconds are identical', () => {
  const { melody, data } = longFixture();
  for (let i = 0; i < 20; i++) data.notes[175 + i].snd[2] = melody[55 + i];
  const score = compileScore(data, 'I');
  const frames = Array.from({ length: 160 }, (_, i) => ({ time: i * .2, chroma: feature(melody[Math.floor(43 + i * .2)]) }));
  const short = alignPhrase(frames.slice(-40), score), long = alignPhrase(frames, score);
  assert.ok(short.some((c) => Math.abs(c.time - 74.8) < .5 && c.score > .9));
  assert.ok(short.some((c) => Math.abs(c.time - 194.8) < .5 && c.score > .9));
  assert.ok(Math.abs(long[0].time - 74.8) < .5);
  assert.ok(long[0].score - long.find((c) => Math.abs(c.time - 194.8) < 3).score > .08);
});

test('three-minute variable-tempo stream retains bounded history and recovers after missing audio', () => {
  const { melody, data } = longFixture(), score = compileScore(data, 'I'), m = new PhraseMatcher(score);
  let position = 20, previous = null, tracking = 0;
  const errors = [], prefix = [];
  for (let i = 0; i < 900; i++) {
    const time = i * .2, speed = time < 45 ? .85 : time < 95 ? 1.15 : .75;
    const missing = time >= 70 && time < 74;
    const r = m.push(time, missing ? null : feature(melody[Math.floor(position)]));
    if (time < 40) prefix.push([r.status, r.position?.time]);
    assert.ok(m.frames.length <= 161);
    if (previous && r.position) assert.ok(r.position.time >= previous.time - 1e-8);
    if (missing) assert.equal(r.status, 'predicting');
    if (time > 20 && r.position) errors.push(Math.abs(r.position.time - position));
    if (r.status === 'tracking') tracking++;
    previous = r.position; position += .2 * speed;
  }
  errors.sort((a, b) => a - b);
  assert.ok(tracking > 500, `tracking frames: ${tracking}`);
  assert.ok(errors[Math.floor(errors.length * .95)] < 1.5, `p95 position error: ${errors[Math.floor(errors.length * .95)]}`);
  assert.equal(m.result.status, 'tracking');
  // Future query frames cannot change an already emitted prefix.
  const early = new PhraseMatcher(score); position = 20;
  for (let i = 0; i < 200; i++) {
    const r = early.push(i * .2, feature(melody[Math.floor(position)]));
    assert.deepEqual([r.status, r.position?.time], prefix[i]); position += .2 * .85;
  }
});

test('retained context cannot confirm the cursor during a long silence', () => {
  const { melody, data } = longFixture(), m = new PhraseMatcher(compileScore(data, 'I'));
  for (let i = 0; i < 170; i++) m.push(i * .2, feature(melody[Math.floor(i * .2)]));
  assert.equal(m.result.status, 'tracking');
  const before = m.result, start = m.lastTime;
  for (let i = 1; i <= 100; i++) {
    const r = m.push(start + i * .2, null);
    assert.equal(r.status, 'predicting');
    assert.ok(Math.abs(r.position.time - before.position.time - i * .2 * before.tempo / 60) < .001);
  }
  assert.ok(m.result.uncertainty > 6);
  assert.ok(m.frames.length <= 161);
});

test('warp cost counts query frames equally; unrelated features cannot gain a slow-path bonus', () => {
  const { melody } = longFixture(60);
  const reference = melody.flatMap((p) => Array.from({ length: 5 }, () => feature(p)));
  // A tiny signal has effectively zero cosine agreement; arbitrary slowing
  // must not turn that zero evidence into a similarity of about one half.
  const frames = Array.from({ length: 160 }, (_, i) => ({ time: i * .2, chroma: Float32Array.from(feature(melody[i % 60]), (v) => v * .0001) }));
  assert.ok(alignChroma(frames, reference).every((c) => c.score < .001));
});

test('coverage reports uninterrupted spans and never joins gaps into a longer match', () => {
  const r = summarizeStates([{ audio: 0, status: 'tracking' }, { audio: .2, status: 'tracking' },
    { audio: .4, status: 'predicting' }, { audio: .6, status: 'tracking' }], .2);
  assert.equal(r.state_seconds.tracking, .6);
  assert.deepEqual(r.longest_uninterrupted.tracking, { start: 0, end: .4, seconds: .4 });
  assert.equal(summarizeStates([{ audio: 1, status: 'tracking' }], 1, 1.3).state_seconds.tracking, .3);
});

test('brief capture gaps keep their elapsed time; leading silence is not phrase context', () => {
  const { data } = longFixture(), m = new PhraseMatcher(compileScore(data, 'I'));
  for (let i = 0; i < 20; i++) m.push(i * .2, null);
  assert.equal(m.frames.length, 0);
  m.push(4, feature(60)); m.push(4.4, feature(64));
  assert.equal(m.frames.length, 3);
  assert.equal(m.frames[1].chroma, null);
  assert.ok(Math.abs(m.frames[1].time - 4.2) < .001);
});

test('a corrected pitch or repeat invalidates a cached profile even when the PDF hash is unchanged', () => {
  const reader = JSON.parse(readFileSync(new URL('../../public/reader/data/dvorak8-trombone1.json', import.meta.url)));
  const profile = JSON.parse(readFileSync(new URL('../../public/reader/following/dvorak8-trombone1.json', import.meta.url)));
  assert.equal(profileMatchesReader(reader, profile), true);
  reader.notes[0].snd[2]++;
  assert.equal(profileMatchesReader(reader, profile), false);
  reader.notes[0].snd[2]--;
  reader.movements[0].timeline.push(reader.movements[0].timeline[0]);
  assert.equal(profileMatchesReader(reader, profile), false);
});
