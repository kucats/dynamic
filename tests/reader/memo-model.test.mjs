import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveMemoAnchor, memoPosition } from '../../public/reader/memo-model.mjs';
const data = { systems: [
  { i: 0, mvt: 'I', page: 1, sys: 1, segs: [[10, 100, '1'], [100, 200, '2–5']] },
  { i: 1, mvt: 'I', page: 2, sys: 1, segs: [[10, 90, '59'], [90, 210, '60–64']] },
  { i: 2, mvt: 'II', page: 3, sys: 1, segs: [[10, 100, '59']] },
] };
test('explicit movement + bar wins over every old page/system/x/y/note field', () => {
  const anchor = { mvt: 'I', bar: 59, page: 1, sys: 1, x: 20, y: 180, note: 1 };
  assert.deepEqual(resolveMemoAnchor(data, anchor), { mvt: 'I', bar: 59 });
  assert.equal(memoPosition(data, anchor).s, 1);
  assert.equal(memoPosition(data, anchor).x, 50);
  assert.equal(anchor.x, 20, 'legacy record is never mutated');
});
test('same bar number in another movement is a different anchor', () => {
  assert.equal(memoPosition(data, { mvt: 'II', bar: 59 }).s, 2);
  assert.equal(memoPosition(data, { mvt: 'III', bar: 59 }), null);
});
test('a multi-rest preserves the chosen exact bar instead of its first bar', () => {
  const at = memoPosition(data, { mvt: 'I', bar: 63 });
  assert.equal(at.segment, 1);
  assert.deepEqual(at.anchor, { mvt: 'I', bar: 63 });
});
test('layout changes locate the bar again, without persisted screen coordinates', () => {
  const changed = structuredClone(data); changed.systems[1].i = 7;
  changed.systems[1].segs[0] = [200, 450, '59'];
  const at = memoPosition(changed, { mvt: 'I', bar: 59, page: 1, sys: 1, x: 20 });
  assert.equal(at.s, 7); assert.equal(at.x, 325);
});
test('missing explicit bar never falls back to a different bar at old coordinates', () => {
  assert.equal(memoPosition(data, { mvt: 'I', bar: 999, page: 1, sys: 1, x: 20 }), null);
});
test('legacy coordinate-only memo is recovered only in an unambiguous single bar', () => {
  assert.deepEqual(resolveMemoAnchor(data, { mvt: 'I', page: 1, sys: 1, x: 20 }), { mvt: 'I', bar: 1 });
  for (const x of [0, 100, 199, 200, NaN, Infinity, '20']) {
    assert.equal(resolveMemoAnchor(data, { mvt: 'I', page: 1, sys: 1, x }), null);
  }
});
test('invalid, fractional, string and out-of-range bars cannot create anchors', () => {
  for (const bar of [0, -1, 2.5, '59', 10000, NaN, Infinity]) {
    assert.equal(resolveMemoAnchor(data, { mvt: 'I', bar, page: 1, sys: 1, x: 20 }), null);
  }
  assert.equal(resolveMemoAnchor(data, null), null);
  assert.equal(resolveMemoAnchor(data, { bar: 59 }), null);
});
