import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { autoPattern, patternFor, parseMeter, planAt, conductGrid, tipAt, nextChange, ictus, guide, displayX } from '../../public/reader/conductor.mjs';

const near = (a, b, e = 1e-9) => Math.abs(a - b) < e;
const spw = (q) => 240 / q;   // seconds per whole note from a quarter-note tempo

test('tempo estimate: fast 2/4 in 1, fast 4/4 in 2, slow 2/4 subdivided, 3/8 waltz in 1, 6/8 in 2', () => {
  assert.equal(autoPattern(0.5, spw(116)), 2);
  assert.equal(autoPattern(0.5, spw(144)), 1);
  assert.equal(autoPattern(0.5, spw(40)), 4);
  assert.equal(autoPattern(1, spw(138)), 2);
  assert.equal(autoPattern(1, spw(66)), 4);
  assert.equal(autoPattern(0.75, spw(100)), 3);
  assert.equal(autoPattern(0.375, spw(75)), 1);            // eighth = 150
  assert.equal(autoPattern(0.375, spw(50)), 3);            // eighth = 100
  assert.equal(autoPattern(0.75, spw(80), parseMeter('6/8')), 2);
  assert.equal(autoPattern(0.75, spw(40), parseMeter('6/8')), 6);
});

test('pattern choice: fitting forced value, then the part plan, then the estimate', () => {
  const plan = [[1, 2], [127, 4]];
  assert.deepEqual(patternFor(130, { len: 1, s: spw(112), plan }), { n: 4, src: 'plan' });
  assert.deepEqual(patternFor(5, { len: 1, s: spw(112), plan }), { n: 2, src: 'plan' });
  assert.deepEqual(patternFor(5, { len: 1, s: spw(112) }), { n: 4, src: 'auto' });
  assert.deepEqual(patternFor(5, { len: 1, s: spw(112), plan, force: '1' }), { n: 1, src: 'forced' });
  assert.deepEqual(patternFor(5, { len: 1, s: spw(112), plan, force: '3' }), { n: 2, src: 'plan' }, '3 does not fit 4/4');
  assert.equal(planAt(plan, 126), 2);
  assert.equal(planAt(plan, 0), null);
});

test('grid divides each bar evenly by its pattern and marks preparatory beats', () => {
  const bars = [{ bar: 1, t: 0, len: 1, s: 2 }, { bar: 2, t: 2, len: 0.5, s: 2 }];
  const pick = (b) => ({ n: b.bar === 1 ? 2 : 1, src: 'plan' });
  const g = conductGrid(bars, pick);
  assert.deepEqual(g.map((b) => [b.bar, b.k, b.n]), [[1, 0, 2], [1, 1, 2], [2, 0, 1]]);
  assert.ok(near(g[1].t, 1) && near(g[1].dur, 1) && near(g[2].dur, 1));
  assert.deepEqual(conductGrid(bars, pick, 1).map((b) => b.k), [1, 0]);
  const pre = conductGrid(bars, pick, 2, 1).filter((b) => b.pre);
  assert.equal(pre.length, 1);
  assert.ok(near(pre[0].t, 1) && pre[0].k === 0 && pre[0].n === 1);
  assert.equal(nextChange(g, 0).bar, 2);
  assert.equal(nextChange(g, 2), null);
});

test('baton tip lands on each ictus at the beat and rebounds between beats', () => {
  const bars = [{ bar: 1, t: 0, len: 1, s: 2 }, { bar: 2, t: 2, len: 1, s: 2 }];
  for (const n of [1, 2, 3, 4]) {
    const g = conductGrid(bars, () => ({ n, src: 'auto' }));
    for (const b of g.slice(0, n)) {
      const tip = tipAt(g, b.t + 1e-9), q = ictus(n, b.k);
      assert.ok(near(tip.x, q.x, 1e-6) && near(tip.y, q.y, 1e-6), `in ${n} beat ${b.k + 1}`);
      const mid = tipAt(g, b.t + b.dur / 2);
      assert.ok(mid.y < q.y, `in ${n}: rebound above the ictus after beat ${b.k + 1}`);
      assert.ok(mid.y > -0.05 && mid.y < 1.05);
    }
  }
  assert.ok(ictus(4, 1).x < 0 && ictus(4, 2).x > 0, 'in 4 goes left then right (conductor view)');
  assert.ok(ictus(4, 0).y > ictus(4, 1).y && ictus(4, 1).y > ictus(4, 2).y && ictus(4, 2).y > ictus(4, 3).y,
    'in 4 rises from downbeat through left and right to the upbeat');
  assert.equal(ictus(4, 3).x, 0, 'beat 4 returns to the centre');
  assert.ok(displayX(ictus(4, 1).x) < 0 && displayX(ictus(4, 2).x) > 0, 'default shows the conductor view');
  assert.ok(displayX(ictus(4, 1).x, true) > 0 && displayX(ictus(4, 2).x, true) < 0, 'players view mirrors it');
  assert.equal(guide(3, 8).length, 25);
});

test('Dvořák 8 trombone I carries a conducting plan in 4/4 and 2/4', () => {
  const d = JSON.parse(fs.readFileSync(new URL('../../public/reader/data/dvorak8-trombone1.json', import.meta.url)));
  const [I, IV] = d.movements;
  assert.deepEqual(I.meters, [[1, '4/4']]);
  assert.ok(I.conduct_note && IV.conduct_note);
  const at = (m, bar) => { const [, len, s] = m.timeline.find((x) => x[0] === bar); return patternFor(bar, { len, s, plan: m.conduct }).n; };
  assert.deepEqual([at(I, 1), at(I, 127), at(I, 143)], [2, 4, 2]);
  assert.deepEqual([at(IV, 1), at(IV, 75), at(IV, 93), at(IV, 356)], [2, 1, 2, 1]);
});
