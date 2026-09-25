import test from 'node:test';
import assert from 'node:assert/strict';
import { beatUnit, beatGrid, createScheduler } from '../../public/reader/metronome.mjs';

const near = (a, b) => Math.abs(a - b) < 1e-9;

test('beat unit follows the bar length in whole notes', () => {
  assert.deepEqual(beatUnit(1), { unit: 0.25, count: 4 });      // 4/4
  assert.deepEqual(beatUnit(0.5), { unit: 0.25, count: 2 });    // 2/4
  assert.deepEqual(beatUnit(0.75), { unit: 0.25, count: 3 });   // 3/4
  assert.deepEqual(beatUnit(0.375), { unit: 0.125, count: 3 }); // 3/8
  assert.deepEqual(beatUnit(0.625), { unit: 0.125, count: 5 }); // 5/8
  assert.deepEqual(beatUnit(0.1875), { unit: 0.0625, count: 3 });
});

test('grid places every beat of every bar and honours tempo per bar', () => {
  const bars = [{ bar: 1, t: 0, len: 1, s: 2 }, { bar: 2, t: 2, len: 0.375, s: 3.2 }];
  const g = beatGrid(bars);
  assert.equal(g.length, 7);
  assert.deepEqual(g.map((b) => b.k), [0, 1, 2, 3, 0, 1, 2]);
  assert.ok(near(g[1].t, 0.5) && near(g[4].t, 2) && near(g[5].t, 2.4));
  assert.ok(near(g[5].dur, 0.4) && g[5].n === 3 && g[5].unit === 0.125);
});

test('starting mid-bar keeps only later beats; count-in fills exactly one bar before the start', () => {
  const bars = [{ bar: 1, t: 0, len: 1, s: 2 }, { bar: 2, t: 2, len: 1, s: 2 }];
  assert.deepEqual(beatGrid(bars, 2.5).map((b) => b.k), [1, 2, 3]);
  const ci = beatGrid(bars, 2, { countIn: true }).filter((b) => b.ci);
  assert.deepEqual(ci.map((b) => b.k), [0, 1, 2, 3]);
  assert.deepEqual(ci.map((b) => b.left), [4, 3, 2, 1]);
  assert.ok(near(ci[0].t, 0) && near(ci[3].t, 1.5));
  const off = beatGrid(bars, 2.25, { countIn: true }).filter((b) => b.ci);
  assert.equal(off.length, 4, 'one bar of clicks on the beat grid');
  assert.ok(off.every((b) => b.t < 2.25 && b.t >= 2.25 - 2 - 1e-9));
  assert.deepEqual(beatGrid(bars, 0, { countIn: true }).filter((b) => b.ci).map((b) => b.t), [-2, -1.5, -1, -0.5]);
});

test('scheduler follows live settings and skips beats in the past', () => {
  const made = [];
  const node = () => ({ connect() {}, start() {}, stop() {}, gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} }, frequency: { setValueAtTime() {}, exponentialRampToValueAtTime() {} } });
  const ctx = { currentTime: 0, createOscillator: () => { const o = node(); made.push(o); return o; }, createGain: node };
  const beats = beatGrid([{ bar: 1, t: 0, len: 1, s: 2 }, { bar: 2, t: 2, len: 1, s: 2 }]);
  const cfg = { on: false, mode: 'beat', vol: 0.5 };
  const sch = createScheduler(ctx, node(), beats, 0.1, () => cfg, 0.2);
  assert.equal(made.length, 0, 'off → silent');
  cfg.on = true; ctx.currentTime = 0.5; made.length = 0;
  sch.stop();
  const sch2 = createScheduler(ctx, node(), beats, 0.1, () => cfg, 1.0);
  assert.equal(made.length, 2, 'beats at 0.6 and 1.1 within look-ahead; 0.1 already past');
  assert.equal(sch2.current(0.65).k, 1);
  assert.equal(sch2.current(0.05), null);
  sch2.stop();
  cfg.mode = 'bar'; made.length = 0;
  const sch3 = createScheduler(ctx, node(), beats, 0, () => cfg, 3);
  assert.equal(made.length, 1, 'only the bar-2 downbeat remains after 0.5 s');
  sch3.stop();
});
