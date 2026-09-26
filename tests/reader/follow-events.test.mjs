import test from 'node:test';
import assert from 'node:assert/strict';
import { compileScore } from '../../public/reader/follow-model.mjs';
import { compilePartEvents, extractEvents, alignEvents, EventSequenceMatcher } from '../../tools/dynamic/following_events.mjs';
import { controlOrder } from '../../tools/dynamic/following_controls.mjs';

const feature = (midi) => {
  const f = new Float32Array(49).fill(-.02); f[midi - 36] = .98; return f;
};
function fixture(count = 160, gap = .8) {
  let seed = 83173;
  const pitches = Array.from({ length: count }, () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return 50 + (seed >>> 16) % 18; });
  return { id: 'original-event-fixture', movements: [{ key: 'I', timeline: pitches.map((_, i) => [i + 1, .25, gap * 4]) }],
    notes: pitches.map((p, i) => ({ mvt: 'I', id: i, bar: i + 1, off: 0, dur: .25, snd: ['', 0, p] })) };
}

test('event template excludes unresolved notes, merges valid ties and preserves repeat occurrences', () => {
  const d = fixture(5);
  d.notes[0].unc = 'unresolved'; d.notes[1].tie = true;
  d.notes[3].snd[2] = d.notes[2].snd[2]; d.notes[3].tie = true;
  d.movements[0].timeline.push(...d.movements[0].timeline.slice(2, 4));
  const e = compilePartEvents(d, compileScore(d, 'I'));
  assert.deepEqual(e.map((v) => [v.bar, v.occurrence]), [[3, 1], [5, 1], [3, 2]]);
  assert.ok(Math.abs(e[0].end - 3.2) < 1e-7);
});

test('segmentation requires a causal second frame and preserves full pitch evidence', () => {
  const frames = [{ time: 0, chroma: feature(50) }];
  assert.equal(extractEvents(frames).length, 0);
  frames.push({ time: .2, chroma: feature(50) }, { time: .4, chroma: feature(52) });
  const before = extractEvents(frames);
  assert.equal(before.length, 1); assert.equal(before[0].pitch, 50);
  frames.push({ time: .6, chroma: feature(52) });
  assert.equal(extractEvents(frames).length, 2);
  assert.equal(before.length, 1); // future input cannot alter an earlier result
  frames.push({ time: .8, chroma: null }, { time: 1, chroma: feature(52) }, { time: 1.2, chroma: feature(52) });
  assert.equal(extractEvents(frames).length, 3);
  assert.equal(extractEvents(Array.from({ length: 100 }, (_, i) => ({ time: i * .2, chroma: feature(55) }))).length, 1);
});

test('event edit path tolerates a substitution, deletion and insertion without dropping elapsed time', () => {
  const d = fixture(), ref = compilePartEvents(d, compileScore(d, 'I'));
  const q = ref.slice(40, 58).filter((_, i) => i !== 7).map((r, i) => ({ time: r.time - 32,
    end: r.time - 32 + .5, pitch: i === 3 ? 79 : r.pitches[0], feature: feature(i === 3 ? 79 : r.pitches[0]) }));
  q.splice(11, 0, { time: (q[10].time + q[11].time) / 2, end: q[10].end, pitch: 77, feature: feature(77) });
  const matches = alignEvents(q, ref, q.at(-1).time + .2);
  assert.ok(matches.length);
  assert.ok(Math.abs(matches[0].time - (ref[57].time + .2)) < .01);
  assert.deepEqual(matches[0].evidence, { matched: 16, substitutions: 1, insertions: 1, deletions: 1, observations: 18 });
});

test('sparse event phrases retain the same evidence score, with rests retained in timing', () => {
  const d = fixture(), ref = compilePartEvents(d, compileScore(d, 'I')).slice(0, 30);
  const q = ref.slice(8, 24).map((r) => ({ time: r.time, end: r.time + .3, pitch: r.pitches[0], feature: feature(r.pitches[0]) }));
  const a = alignEvents(q, ref, q.at(-1).time + .2)[0];
  const stretch = (e) => ({ ...e, time: e.time * 3, end: e.end * 3 });
  const b = alignEvents(q.map(stretch), ref.map(stretch), q.at(-1).time * 3 + .2)[0];
  assert.ok(a && b); assert.ok(Math.abs(a.score - b.score) < 1e-7);
  const collapsed = q.map((e, i) => ({ ...e, time: i * .15, end: i * .15 + .1 }));
  assert.equal(alignEvents(collapsed, ref, collapsed.at(-1).time + .05).length, 0);
});

test('ambiguous repeated phrases remain candidates and a static tone never acquires', () => {
  const d = fixture(20), ref = compilePartEvents(d, compileScore(d, 'I'));
  const q = ref.slice(0, 14).map((r) => ({ time: r.time, end: r.time + .5, pitch: r.pitches[0], feature: feature(r.pitches[0]) }));
  const repeated = [...ref, ...ref.map((r) => ({ ...r, time: r.time + 30, end: r.end + 30 }))];
  const matches = alignEvents(q, repeated, q.at(-1).time + .2);
  assert.ok(matches.length >= 2); assert.ok(Math.abs(matches[0].score - matches[1].score) < 1e-7);
  const m = new EventSequenceMatcher(compileScore(d, 'I'), d);
  for (let i = 0; i < 200; i++) m.push(i * .2, feature(55));
  assert.equal(m.result.position, null);
});

test('event following retains manual priority, rest prediction and bounded history', () => {
  const d = fixture(220), s = compileScore(d, 'I'), m = new EventSequenceMatcher(s, d);
  m.override(20, 0);
  let previous = 20;
  for (let i = 1; i < 600; i++) {
    const t = i * .2;
    // Strong evidence for a distant phrase is deliberately incompatible with manual position.
    const p = d.notes[Math.floor((t + 50) / .8)]?.snd[2] ?? 55;
    const r = m.push(t, t > 30 && t < 40 ? null : feature(p));
    assert.equal(r.manual, true); assert.ok(r.position.time >= previous - 1e-7);
    assert.ok(Math.abs(r.position.time - (20 + t)) < 1);
    if (t > 30 && t < 40) assert.equal(r.status, 'predicting');
    assert.ok(m.frames.length <= 161); previous = r.position.time;
  }
  const stopped = m.hold().position.time;
  assert.ok(Math.abs(m.push(0, null).position.time - stopped) < 1e-7);
});

test('an original played phrase acquires automatically and resumes after a rest', () => {
  const d = fixture(240), s = compileScore(d, 'I'), m = new EventSequenceMatcher(s, d);
  let accepted = 0, afterRest = 0;
  const errors = [];
  for (let i = 0; i < 500; i++) {
    const t = i * .2, target = 16 + t, index = Math.floor((target + 1e-7) / .8);
    let f = feature(d.notes[index].snd[2]);
    if (t > 20 && index % 17 === 0) f = feature(79);
    if (t > 20 && index % 19 === 0) f = null;
    if (t >= 50 && t < 56) f = null;
    const r = m.push(t, f);
    if (r.status === 'tracking') { accepted++; if (t > 56) afterRest++; }
    if (r.position) errors.push(Math.abs(r.position.time - target));
    if (t >= 50 && t < 56) assert.equal(r.status, 'predicting');
  }
  errors.sort((a, b) => a - b);
  assert.ok(accepted > 50, `accepted ${accepted}`); assert.ok(afterRest > 10, `after rest ${afterRest}`);
  assert.ok(errors[Math.floor(errors.length * .95)] < 1, `p95 ${errors[Math.floor(errors.length * .95)]}`);
});

test('pitch-order negative control preserves plausible event intervals but cannot acquire this original phrase', () => {
  const d = fixture(), ref = compilePartEvents(d, compileScore(d, 'I'));
  const q = ref.slice(30, 54).map((r, i, all) => ({ time: r.time, end: r.time + .5,
    pitch: all[all.length - i - 1].pitches[0], feature: feature(all[all.length - i - 1].pitches[0]) }));
  assert.equal(alignEvents(q, ref, q.at(-1).time + .2).length, 0);
});

test('two-second block control keeps event fragments and every frame, including a partial last block', () => {
  const order = controlOrder(137, 'shuffle-blocks');
  assert.deepEqual(order, controlOrder(137, 'shuffle-blocks'));
  assert.deepEqual([...order].sort((a, b) => a - b), Array.from({ length: 137 }, (_, i) => i));
  assert.notDeepEqual(order, controlOrder(137, 'none'));
  for (let start = 0; start < 137; start += 10) {
    const index = order.indexOf(start);
    assert.deepEqual(order.slice(index, index + Math.min(10, 137 - start)),
      Array.from({ length: Math.min(10, 137 - start) }, (_, i) => start + i));
  }
});
