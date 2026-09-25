/* DYNAMIC reader — trombone player kinematics (no rendering; shared by trombone3d.js and tests).
 *
 * World frame: the player faces +X, +Y is up, +Z is the player's right, feet at y = 0 (metres).
 * Instrument frame: origin at the mouthpiece rim on the lips, +X along the slide, rotated
 * down by SLIDE_PITCH. Slide distances are an illustrative model, not an intonation chart. */

// Acoustic length of a B♭ tenor trombone in first position (≈ 2.74 m). Each position lowers
// the pitch by a semitone; the slide has two legs, so it moves half the added tube length.
export const BASE_LENGTH_M = 2.74;
export const SLIDE_PITCH = 9 * Math.PI / 180;         // slide points slightly down
export const LIPS = [0.125, 1.565, 0];
export const UPPER_ARM = 0.315, FOREARM = 0.28;
export const SHOULDER_R = [0, 1.43, 0.185], SHOULDER_L = [0, 1.43, -0.185];
export const MAX_TWIST = 18 * Math.PI / 180;           // torso turns to bring the right shoulder forward
export const MAX_PROTRACTION = 0.09;                   // shoulder blade reaches forward at 6th–7th

// Instrument-frame geometry
export const TUBE_A = [0, 0], TUBE_B = [-0.07, -0.07];  // [y, z] of the mouthpiece-side and bell-side slide tubes
export const INNER_START = 0.075, INNER_END = 0.715;    // exposed inner slide (nickel silver)
export const OUTER_START = 0.098, OUTER_END = 0.742;    // outer slide straight tubes at first position
export const BRACE_X = 0.12;                            // right-hand brace at first position
export const BELL_AXIS = [0.075, -0.15], BELL_RIM_X = 0.33, BELL_RIM_R = 0.108, BELL_LENGTH = 0.46;
export const TUNING_BOW_X = -0.27;
export const RIGHT_GRIP = [BRACE_X, (TUBE_A[0] + TUBE_B[0]) / 2, (TUBE_A[1] + TUBE_B[1]) / 2];
export const LEFT_GRIP = [0.075, -0.06, -0.09];
export const LEFT_WRIST = [0.055, -0.145, -0.105];

export function extensionFor(position) {
  const p = Number(position);
  if (!Number.isFinite(p) || p < 1 || p > 7) throw new RangeError('position must be 1–7');
  return BASE_LENGTH_M / 2 * (2 ** ((p - 1) / 12) - 1);
}
export const MAX_EXTENSION = extensionFor(7);

/** Reader note → slide position (1–7) or null. Accepts numbers or strings such as "3", "♭4", "6(T)". */
export function parsePosition(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'number') return value >= 1 && value <= 7 ? value : null;
  const m = String(value).match(/[1-7](?:\.\d+)?/);
  return m ? Number(m[0]) : null;
}

/** Minimum-jerk profile: smooth start and stop, like a practised slide arm. */
export function minJerk(u) {
  const t = Math.max(0, Math.min(1, u));
  return t * t * t * (10 - 15 * t + 6 * t * t);
}
/** Seconds for a slide change; longer throws take longer but stay quick. */
export function moveDuration(from, to) {
  return Math.min(0.3, 0.09 + 0.22 * Math.abs(to - from) / MAX_EXTENSION);
}

const lerp = (a, b, t) => a + (b - a) * t;
const sub = (a, b) => a.map((n, i) => n - b[i]);
const add = (a, b) => a.map((n, i) => n + b[i]);
const scale = (a, s) => a.map((n) => n * s);
const dot = (a, b) => a.reduce((s, n, i) => s + n * b[i], 0);
const len = (a) => Math.hypot(...a);
export const distance = (a, b) => len(sub(a, b));

/** Instrument frame → world frame (pitch about Z, then translate to the lips). */
export function toWorld(p) {
  const c = Math.cos(SLIDE_PITCH), s = Math.sin(SLIDE_PITCH);
  return [LIPS[0] + p[0] * c + p[1] * s, LIPS[1] - p[0] * s + p[1] * c, LIPS[2] + p[2]];
}

/** How far into the 5th→7th reach the pose is (0 before fifth position). */
export function reachFactor(extension) {
  const five = extensionFor(5);
  return Math.max(0, Math.min(1, (extension - five) / (MAX_EXTENSION - five)));
}

/** Right wrist in the instrument frame: hanging below the brace in close positions,
 * in line with the arm (fingertip grip) at the far positions. */
export function rightWristLocal(extension) {
  const u = Math.min(1, extension / MAX_EXTENSION);
  const near = [-0.045, -0.075, 0.035], far = [-0.1, -0.012, 0.012];
  return add(RIGHT_GRIP, [extension + lerp(near[0], far[0], u), lerp(near[1], far[1], u), lerp(near[2], far[2], u)]);
}

/** Two-bone IK with a pole vector; returns the elbow. Clamps an out-of-reach target. */
export function elbowFor(shoulder, wrist, pole, l1 = UPPER_ARM, l2 = FOREARM) {
  const delta = sub(wrist, shoulder);
  const d = Math.min(Math.max(len(delta), Math.abs(l1 - l2) + 1e-6), l1 + l2 - 1e-6);
  const dir = scale(delta, 1 / (len(delta) || 1));
  const a = (l1 * l1 - l2 * l2 + d * d) / (2 * d);
  const h = Math.sqrt(Math.max(0, l1 * l1 - a * a));
  let perp = sub(pole, scale(dir, dot(pole, dir)));
  perp = scale(perp, 1 / (len(perp) || 1));
  return add(add(shoulder, scale(dir, a)), scale(perp, h));
}

/** Full-body pose for a slide extension in metres. */
export function solvePose(extension) {
  const reach = reachFactor(extension);
  const twist = MAX_TWIST * reach;
  const rs = [SHOULDER_R[0] + SHOULDER_R[2] * Math.sin(twist), SHOULDER_R[1], SHOULDER_R[2] * Math.cos(twist)];
  const ls = [SHOULDER_L[0] + SHOULDER_L[2] * Math.sin(twist), SHOULDER_L[1], SHOULDER_L[2] * Math.cos(twist)];
  const rightWrist = toWorld(rightWristLocal(extension));
  // The shoulder blade slides forward only as much as the arm needs (never more than MAX_PROTRACTION).
  const need = Math.max(0, distance(rs, rightWrist) - 0.985 * (UPPER_ARM + FOREARM));
  const toWrist = sub(rightWrist, rs), protraction = Math.min(MAX_PROTRACTION, need);
  const rightShoulder = add(rs, scale(toWrist, protraction / len(toWrist)));
  const rightElbow = elbowFor(rightShoulder, rightWrist, [-0.25, -1, 0.5]);
  const leftWrist = toWorld(LEFT_WRIST);
  const leftElbow = elbowFor(ls, leftWrist, [0.25, -1, -0.3]);
  return { extension, twist, protraction, rightShoulder, rightElbow, rightWrist, leftShoulder: ls, leftElbow, leftWrist,
    rightGrip: toWorld(add(RIGHT_GRIP, [extension, 0, 0])), leftGrip: toWorld(LEFT_GRIP) };
}
