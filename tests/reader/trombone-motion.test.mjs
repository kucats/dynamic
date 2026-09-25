import test from 'node:test';
import assert from 'node:assert/strict';
import * as K from '../../public/reader/trombone-motion.js';

const near = (a, b, eps = 1e-9) => Math.abs(a - b) < eps;

test('slide extensions grow by semitone ratios from first position', () => {
  assert.equal(K.extensionFor(1), 0);
  const ext = [1, 2, 3, 4, 5, 6, 7].map(K.extensionFor);
  for (let i = 1; i < 7; i++) assert.ok(ext[i] - ext[i - 1] > (ext[i - 1] - (ext[i - 2] ?? 0)) - 1e-12, 'spacing increases');
  assert.ok(ext[6] > 0.55 && ext[6] < 0.6, `seventh ≈ 57 cm, got ${ext[6]}`);
  assert.throws(() => K.extensionFor(0), RangeError);
  assert.throws(() => K.extensionFor(8), RangeError);
});

test('reader position values are parsed without guessing', () => {
  assert.equal(K.parsePosition(3), 3);
  assert.equal(K.parsePosition('4'), 4);
  assert.equal(K.parsePosition('♭6'), 6);
  assert.equal(K.parsePosition(null), null);
  assert.equal(K.parsePosition(''), null);
  assert.equal(K.parsePosition('T'), null);
  assert.equal(K.parsePosition(9), null);
});

test('arm bones keep their length and every position is within reach', () => {
  for (let i = 0; i <= 100; i++) {
    const e = K.MAX_EXTENSION * i / 100, p = K.solvePose(e);
    assert.ok(near(K.distance(p.rightShoulder, p.rightElbow), K.UPPER_ARM, 1e-6));
    assert.ok(near(K.distance(p.rightElbow, p.rightWrist), K.FOREARM, 1e-6));
    assert.ok(K.distance(p.rightShoulder, p.rightWrist) <= K.UPPER_ARM + K.FOREARM, `wrist reachable at ${e}`);
    assert.ok(p.protraction <= K.MAX_PROTRACTION + 1e-12);
    assert.ok(p.rightElbow[1] < p.rightShoulder[1] + 0.01, 'right elbow does not rise above the shoulder');
    assert.ok(near(K.distance(p.leftShoulder, p.leftElbow), K.UPPER_ARM, 1e-6));
    assert.ok(near(K.distance(p.leftElbow, p.leftWrist), K.FOREARM, 1e-6));
  }
});

test('landmarks: third just before the bell, fourth past it, seventh with slide left in the stocking', () => {
  const bellX = K.toWorld([K.BELL_RIM_X, ...K.BELL_AXIS])[0];
  const grip = (n) => K.solvePose(K.extensionFor(n)).rightGrip[0];
  assert.ok(grip(3) < bellX && grip(4) > bellX, `bell rim ${bellX} between third ${grip(3)} and fourth ${grip(4)}`);
  const overlap = K.INNER_END - (K.OUTER_START + K.MAX_EXTENSION);
  assert.ok(overlap > 0.02 && overlap < 0.06, `inner/outer overlap at seventh ${overlap}`);
  assert.ok(K.solvePose(K.extensionFor(1)).protraction === 0, 'no reach needed in first position');
  assert.ok(K.solvePose(K.extensionFor(7)).twist > 0, 'body turns into seventh');
});

test('slide motion is smooth and quick', () => {
  assert.equal(K.minJerk(0), 0);
  assert.equal(K.minJerk(1), 1);
  assert.ok(near(K.minJerk(0.5), 0.5));
  assert.ok(K.moveDuration(0, K.MAX_EXTENSION) <= 0.3);
  assert.ok(K.moveDuration(0, K.extensionFor(2)) < K.moveDuration(0, K.extensionFor(6)));
});
