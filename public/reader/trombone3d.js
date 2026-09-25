/* DYNAMIC reader — 3D trombone player (loaded only when the 3D mode is switched on).
 * A procedural Three.js figure whose right arm follows the slide. Geometry and arm
 * kinematics live in trombone-motion.js; this file only builds and animates meshes. */
import * as THREE from './vendor/three/three.module.min.js';
import * as K from './trombone-motion.js';

const V = (a) => new THREE.Vector3(a[0], a[1], a[2]);
const UP = new THREE.Vector3(0, 1, 0);

function materials() {
  const m = (color, roughness = 0.75, metalness = 0, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness, metalness, ...extra });
  return {
    skin: m('#e2ae8c', 0.62), skinShade: m('#c98f6e', 0.7), lip: m('#b8695a', 0.5),
    hair: m('#2b221c', 0.85), brow: m('#2b221c', 0.9), eyeWhite: m('#f7f4ee', 0.3), iris: m('#3a2a1e', 0.25),
    jacket: m('#262d3f', 0.72), jacketDark: m('#141823', 0.7), lapel: m('#252b3b', 0.35), shirt: m('#f4f6fa', 0.6),
    trouser: m('#1a1e2a', 0.78), shoe: m('#0e0f13', 0.28, 0.1), tie: m('#0e1016', 0.4),
    brass: m('#e1b24f', 0.24, 0.9, { envMapIntensity: 1.2 }), brassDark: m('#b8862d', 0.3, 0.9),
    nickel: m('#dfe3e6', 0.2, 0.95, { envMapIntensity: 1.1 }), cork: m('#2b2b2b', 0.6),
    bellInside: m('#d9a444', 0.3, 0.85, { side: THREE.BackSide }),
  };
}

// ---------- small geometry helpers ----------
function mesh(geo, mat, parent, pos) {
  const o = new THREE.Mesh(geo, mat); o.castShadow = true; o.receiveShadow = true;
  if (pos) o.position.copy(V(pos));
  parent.add(o); return o;
}
function ellipsoid(parent, mat, pos, s, seg = 28) {
  const o = mesh(new THREE.SphereGeometry(1, seg, Math.round(seg * 0.75)), mat, parent, pos); o.scale.set(...s); return o;
}
/** Tapered segment from a to b (radii ra at a, rb at b). */
function segment(parent, mat, a, b, ra, rb = ra, radial = 18) {
  const o = mesh(new THREE.CylinderGeometry(rb, ra, 1, radial, 1, true), mat, parent);
  placeSegment(o, a, b); return o;
}
function placeSegment(o, a, b) {
  const va = a.isVector3 ? a : V(a), vb = b.isVector3 ? b : V(b);
  const d = vb.clone().sub(va), l = d.length();
  o.position.copy(va).addScaledVector(d, 0.5); o.scale.set(1, Math.max(l, 1e-4), 1);
  o.quaternion.setFromUnitVectors(UP, d.normalize());
}
function tube(parent, mat, pts, r, seg = 64, radial = 14, closed = false) {
  const curve = new THREE.CatmullRomCurve3(pts.map((p) => (p.isVector3 ? p : V(p))), closed, 'centripetal');
  return mesh(new THREE.TubeGeometry(curve, seg, r, radial, closed), mat, parent);
}
/** Semicircular crook from p (start) bulging along dir, ending at q. */
function crook(p, q, dir, n = 24) {
  const c = V(p).add(V(q)).multiplyScalar(0.5), half = V(p).sub(c), r = half.length(), f = V(dir).normalize();
  const pts = [];
  for (let i = 0; i <= n; i++) { const a = (Math.PI * i) / n; pts.push(c.clone().addScaledVector(half, Math.cos(a)).addScaledVector(f, Math.sin(a) * r)); }
  return pts;
}

// ---------- environment (no external HDR: a soft studio built from panels) ----------
function studio(renderer) {
  const env = new THREE.Scene();
  const box = new THREE.Mesh(new THREE.BoxGeometry(10, 6, 10), new THREE.MeshBasicMaterial({ color: '#cfd8e3', side: THREE.BackSide }));
  env.add(box);
  const panel = (w, h, pos, color, intensity) => {
    const p = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(intensity), side: THREE.DoubleSide }));
    p.position.set(...pos); p.lookAt(0, 1, 0); env.add(p);
  };
  panel(4, 2, [0, 2.9, 0], '#ffffff', 3.2);
  panel(2.5, 2.5, [4.5, 1.8, 2], '#fff4df', 2.6);
  panel(2, 3, [-4.5, 1.5, -1], '#dfeaff', 1.6);
  panel(3, 1, [1, 0.3, 4.5], '#ffffff', 1.2);
  env.add(new THREE.Mesh(new THREE.PlaneGeometry(10, 10), new THREE.MeshBasicMaterial({ color: '#8a8f96' })).rotateX(-Math.PI / 2).translateZ(-2.9));
  const pmrem = new THREE.PMREMGenerator(renderer);
  const tex = pmrem.fromScene(env, 0.035).texture; pmrem.dispose();
  env.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
  return tex;
}

// ---------- trombone (instrument frame, see trombone-motion.js) ----------
function buildTrombone(M) {
  const g = new THREE.Group(), outer = new THREE.Group();
  g.name = 'trombone'; outer.name = 'outer-slide';
  const A = (x) => [x, K.TUBE_A[0], K.TUBE_A[1]], B = (x) => [x, K.TUBE_B[0], K.TUBE_B[1]];
  const bell = (x, dy = 0, dz = 0) => [x, K.BELL_AXIS[0] + dy, K.BELL_AXIS[1] + dz];
  // Mouthpiece: rim, cup, shank.
  const mp = [[0.0125, 0], [0.0135, 0.004], [0.012, 0.009], [0.0085, 0.02], [0.0048, 0.034], [0.0056, 0.05], [0.0062, 0.085], [0.0052, 0.085]].map(([r, y]) => new THREE.Vector2(r, y));
  const mouthpiece = mesh(new THREE.LatheGeometry(mp, 28), M.nickel, g); mouthpiece.rotation.z = -Math.PI / 2;
  // Inner slide (nickel silver), lock and first brace.
  for (const T of [A, B]) segment(g, M.nickel, T(K.INNER_START), T(K.INNER_END), 0.0062);
  segment(g, M.nickel, A(0.06), A(0.094), 0.0078);                        // mouthpiece receiver
  segment(g, M.brass, B(0.02), B(K.INNER_START + 0.01), 0.0085);           // slide receiver on the bell side
  segment(g, M.nickel, A(0.07), B(0.07), 0.0055);                          // inner slide brace
  ellipsoid(g, M.brass, B(0.05), [0.016, 0.013, 0.013], 16);               // slide lock nut
  // Bell section: back from the slide, round the tuning slide over the left shoulder, forward to the bell.
  const back = [B(0.03), [-0.01, -0.06, -0.1], [-0.06, -0.04, -0.14], [-0.14, -0.035, -0.15]];
  tube(g, M.brass, [...back, [K.TUNING_BOW_X + 0.07, -0.035, -0.15]], 0.0068, 48);
  const bowLow = [K.TUNING_BOW_X + 0.07, -0.035, -0.15], bowHigh = [K.TUNING_BOW_X + 0.07, K.BELL_AXIS[0], K.BELL_AXIS[1]];
  const bow = [bowLow, ...crook(bowLow, bowHigh, [-1, 0, 0], 20).slice(1)];
  tube(g, M.nickel, bow, 0.0072, 40);
  segment(g, M.nickel, bowLow, [-0.14, -0.035, -0.15], 0.0082);            // tuning slide stockings
  segment(g, M.nickel, bowHigh, bell(-0.14), 0.0082);
  const bellStart = K.BELL_RIM_X - K.BELL_LENGTH;
  segment(g, M.brass, bell(-0.14), bell(bellStart), 0.0075);
  segment(g, M.brass, [-0.12, -0.035, -0.15], bell(-0.12), 0.004);         // tuning slide brace
  // Bell flare: slow growth, then a fast flare in the last few centimetres.
  const prof = [];
  for (let i = 0; i <= 40; i++) { const u = i / 40; prof.push(new THREE.Vector2(0.0078 + 0.028 * u * u + (K.BELL_RIM_R - 0.0358) * u ** 7.5, u * K.BELL_LENGTH)); }
  const flare = new THREE.LatheGeometry(prof, 64);
  const bellMesh = mesh(flare, M.brass, g, bell(bellStart)); bellMesh.rotation.z = -Math.PI / 2;
  const bellIn = mesh(flare, M.bellInside, g, bell(bellStart)); bellIn.rotation.z = -Math.PI / 2; bellIn.castShadow = false;
  const rim = mesh(new THREE.TorusGeometry(K.BELL_RIM_R, 0.0032, 10, 96), M.brass, g, bell(K.BELL_RIM_X)); rim.rotation.y = Math.PI / 2;
  // Bell brace to the slide (the left hand holds here).
  segment(g, M.brass, bell(0.06), [0.07, -0.045, -0.08], 0.0042);
  ellipsoid(g, M.brass, bell(0.06), [0.01, 0.01, 0.01], 12);
  // Outer slide: one rigid U, moved along X without scaling.
  for (const T of [A, B]) {
    segment(outer, M.brass, T(K.OUTER_START), T(K.OUTER_END), 0.0076);
    segment(outer, M.nickel, T(K.OUTER_START - 0.006), T(K.OUTER_START + 0.03), 0.0086);   // stocking sleeve
    segment(outer, M.nickel, T(K.OUTER_END - 0.035), T(K.OUTER_END), 0.0084);
  }
  const bumper = crook(A(K.OUTER_END), B(K.OUTER_END), [1, 0, 0], 28);
  tube(outer, M.brass, bumper, 0.0076, 40);
  mesh(new THREE.SphereGeometry(0.009, 14, 10), M.cork, outer, [K.OUTER_END + 0.052, (K.TUBE_A[0] + K.TUBE_B[0]) / 2, (K.TUBE_A[1] + K.TUBE_B[1]) / 2]);  // rubber tip
  segment(outer, M.brass, A(K.BRACE_X), B(K.BRACE_X), 0.0055);              // hand brace
  segment(outer, M.brass, A(K.OUTER_END - 0.05), B(K.OUTER_END - 0.05), 0.004);
  const wk = segment(outer, M.brassDark, B(K.OUTER_END + 0.03), [K.OUTER_END + 0.015, K.TUBE_B[0] - 0.03, K.TUBE_B[1] - 0.02], 0.0025); wk.castShadow = false;  // water key
  g.add(outer);
  return { group: g, outer, bellMouth: bell(K.BELL_RIM_X) };
}

// ---------- hands ----------
/** A gripping hand in a local frame: +X from wrist to knuckles, +Z along the held bar. */
function buildHand(M, side) {
  const h = new THREE.Group();
  ellipsoid(h, M.skin, [0.045, 0, 0], [0.05, 0.02, 0.043], 18);
  const s = side === 'left' ? -1 : 1;
  for (let i = 0; i < 4; i++) {
    const z = (-0.027 + i * 0.018) * s, l = [0.024, 0.027, 0.026, 0.021][i];
    const pts = [[0.085, 0.004, z], [0.085 + l, 0.004, z], [0.1 + l, -0.022, z], [0.085 + l * 0.6, -0.042, z * 0.95], [0.075, -0.035, z * 0.9]];
    tube(h, M.skin, pts, 0.0082 - i * 0.0006, 16, 8);
  }
  tube(h, M.skin, [[0.03, -0.012, 0.035 * s], [0.06, -0.03, 0.045 * s], [0.085, -0.045, 0.03 * s]], 0.0095, 12, 8);   // thumb
  segment(h, M.shirt, [-0.045, 0, 0], [0.004, 0, 0], 0.036, 0.033);        // shirt cuff
  segment(h, M.jacket, [-0.09, 0, 0], [-0.04, 0, 0], 0.045, 0.043);        // sleeve end
  return h;
}
const _m = new THREE.Matrix4(), _x = new THREE.Vector3(), _y = new THREE.Vector3(), _z = new THREE.Vector3();
function orientHand(hand, wrist, grip, barDir) {
  _x.copy(grip).sub(wrist).normalize();
  _z.copy(barDir).addScaledVector(_x, -barDir.dot(_x)).normalize();
  _y.crossVectors(_z, _x);
  _m.makeBasis(_x, _y, _z); hand.quaternion.setFromRotationMatrix(_m); hand.position.copy(wrist);
  const l = grip.distanceTo(wrist) / 0.09; hand.scale.set(Math.max(0.85, Math.min(1.15, l)), 1, 1);
}

// ---------- player ----------
function buildPlayer(M) {
  const root = new THREE.Group(), lower = new THREE.Group(), upper = new THREE.Group(), chest = new THREE.Group(), head = new THREE.Group();
  root.add(lower, upper); upper.add(chest, head);
  upper.position.set(0, 0.98, 0);      // upper body pivots at the hips
  const U = (p) => [p[0], p[1] - 0.98, p[2]];
  // Legs and shoes (weight slightly on the back foot, feet apart).
  for (const [z, fx] of [[0.11, 0.03], [-0.11, -0.07]]) {
    segment(lower, M.trouser, [fx, 0.09, z], [fx + 0.015, 0.5, z], 0.052, 0.062);
    segment(lower, M.trouser, [fx + 0.015, 0.5, z], [0, 0.95, z * 0.9], 0.064, 0.085);
    ellipsoid(lower, M.trouser, [fx + 0.015, 0.5, z], [0.064, 0.05, 0.064], 16);
    ellipsoid(lower, M.shoe, [fx + 0.06, 0.04, z * 1.05], [0.135, 0.045, 0.052], 20);
  }
  ellipsoid(lower, M.trouser, [0, 0.93, 0], [0.12, 0.09, 0.16]);
  // Torso: lathe profile, flattened front to back, with jacket, shirt front, bow tie.
  const tp = [[0.001, 0], [0.17, 0.0], [0.168, 0.1], [0.155, 0.2], [0.152, 0.32], [0.168, 0.45], [0.185, 0.54], [0.17, 0.59], [0.1, 0.62], [0.001, 0.62]].map(([r, y]) => new THREE.Vector2(r, y));
  const torso = mesh(new THREE.LatheGeometry(tp, 40), M.jacket, chest, U([0, 0.84, 0])); torso.scale.z = 0.64;
  for (const s of [-1, 1]) { const vent = segment(chest, M.jacketDark, U([0.105, 0.845, 0.004 * s]), U([0.098, 1.04, 0.012 * s]), 0.0025); vent.castShadow = false; }
  const shirt = ellipsoid(chest, M.shirt, U([0.07, 1.36, 0]), [0.05, 0.1, 0.055]); shirt.rotation.z = -0.15;
  for (const s of [-1, 1]) {
    const lap = mesh(new THREE.BoxGeometry(0.012, 0.26, 0.05), M.lapel, chest, U([0.1, 1.3, 0.05 * s]));
    lap.rotation.set(0.35 * s, 0, -0.08);
    ellipsoid(chest, M.tie, U([0.113, 1.425, 0.022 * s]), [0.012, 0.016, 0.022], 12);
  }
  ellipsoid(chest, M.tie, U([0.117, 1.425, 0]), [0.01, 0.011, 0.01], 10);
  for (const y of [1.1, 1.18]) ellipsoid(chest, M.jacketDark, U([0.1, y, 0.018]), [0.006, 0.009, 0.009], 8);
  segment(chest, M.skin, U([0.0, 1.45, 0]), U([0.03, 1.56, 0]), 0.05, 0.047);   // neck
  segment(chest, M.shirt, U([0.0, 1.44, 0]), U([0.01, 1.485, 0]), 0.058, 0.055); // collar
  // Head (faces +X), lips at LIPS.
  const H = (p) => U(p);
  ellipsoid(head, M.skin, H([0.035, 1.64, 0]), [0.098, 0.115, 0.085], 36);         // cranium
  ellipsoid(head, M.skin, H([0.075, 1.575, 0]), [0.06, 0.055, 0.063], 28);         // jaw
  ellipsoid(head, M.skin, H([0.108, 1.585, 0]), [0.018, 0.024, 0.036], 16);        // upper lip / embouchure
  ellipsoid(head, M.lip, H([K.LIPS[0] - 0.006, K.LIPS[1], 0]), [0.008, 0.009, 0.022], 12);
  ellipsoid(head, M.skin, H([0.106, 1.545, 0]), [0.022, 0.019, 0.03], 14);        // chin
  const nose = ellipsoid(head, M.skin, H([0.138, 1.622, 0]), [0.022, 0.03, 0.014], 14); nose.rotation.z = -0.3;
  for (const s of [-1, 1]) {
    ellipsoid(head, M.skin, H([0.07, 1.605, 0.05 * s]), [0.03, 0.03, 0.022], 14);   // cheeks stay firm (not puffed)
    ellipsoid(head, M.eyeWhite, H([0.119, 1.658, 0.034 * s]), [0.01, 0.0095, 0.014], 12);
    ellipsoid(head, M.iris, H([0.1275, 1.657, 0.033 * s]), [0.003, 0.0068, 0.0068], 10);
    const lid = ellipsoid(head, M.skin, H([0.12, 1.665, 0.034 * s]), [0.0108, 0.0055, 0.0148], 12); lid.castShadow = false;
    const brow = segment(head, M.brow, H([0.132, 1.682, 0.016 * s]), H([0.122, 1.686, 0.05 * s]), 0.004); brow.castShadow = false;
    const ear = ellipsoid(head, M.skinShade, H([0.02, 1.63, 0.084 * s]), [0.02, 0.03, 0.009], 12); ear.rotation.z = 0.15;
  }
  const hairCap = mesh(new THREE.SphereGeometry(1, 36, 24, 0, Math.PI * 2, 0, Math.PI * 0.5), M.hair, head, H([0.03, 1.655, 0]));
  hairCap.scale.set(0.104, 0.118, 0.091); hairCap.rotation.z = 0.5;
  const fringe = ellipsoid(head, M.hair, H([0.07, 1.735, 0.012]), [0.05, 0.022, 0.08], 20); fringe.rotation.set(0.12, 0, -0.45);
  ellipsoid(head, M.hair, H([-0.03, 1.64, 0]), [0.06, 0.09, 0.086], 20);             // back of the head
  // Arms: bones get repositioned every frame.
  const arm = (side) => {
    const o = {};
    o.shoulder = ellipsoid(upper, M.jacket, [0, 0, 0], [0.062, 0.06, 0.06], 20);
    o.upper = segment(upper, M.jacket, [0, 0, 0], [0, -0.3, 0], 0.054, 0.046);
    o.elbow = ellipsoid(upper, M.jacket, [0, 0, 0], [0.048, 0.048, 0.048], 16);
    o.fore = segment(upper, M.jacket, [0, 0, 0], [0, -0.28, 0], 0.046, 0.04);
    o.hand = buildHand(M, side); upper.add(o.hand);
    return o;
  };
  const right = arm('right'), left = arm('left');
  ellipsoid(chest, M.jacket, U([0.0, 1.43, 0.15]), [0.07, 0.05, 0.06], 16);        // shoulder pads
  ellipsoid(chest, M.jacket, U([0.0, 1.43, -0.15]), [0.07, 0.05, 0.06], 16);
  return { root, upper, chest, head, right, left, toUpper: U };
}

export function createTrombonePlayer(canvas, { onError } = {}) {
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'low-power' }); }
  catch (e) { onError?.(e); throw e; }
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#e8eff8');
  scene.environment = studio(renderer);
  scene.add(new THREE.HemisphereLight('#ffffff', '#9aa7b8', 0.6));
  const key = new THREE.DirectionalLight('#fff3e2', 2.0);
  key.position.set(1.6, 3.6, 2.2); key.castShadow = true; key.shadow.mapSize.set(1024, 1024);
  Object.assign(key.shadow.camera, { left: -1.4, right: 1.6, top: 2.2, bottom: -0.3, near: 0.5, far: 8 });
  key.shadow.normalBias = 0.02; key.target.position.set(0.3, 1, 0); scene.add(key, key.target);
  const rimLight = new THREE.DirectionalLight('#d6e6ff', 1.1); rimLight.position.set(-2, 2.5, -2); scene.add(rimLight);
  const floor = new THREE.Mesh(new THREE.CircleGeometry(1.6, 64), new THREE.MeshStandardMaterial({ color: '#dfe7f1', roughness: 0.95 }));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; floor.position.set(0.25, 0, 0); scene.add(floor);

  const M = materials();
  const P = buildPlayer(M); scene.add(P.root);
  const T = buildTrombone(M);
  // The instrument hangs off the head/upper body so a lean carries it along.
  T.group.position.copy(V(P.toUpper(K.LIPS))); T.group.rotation.z = -K.SLIDE_PITCH; P.upper.add(T.group);
  // Sound rings from the bell while a note sounds.
  const ringMat = new THREE.MeshBasicMaterial({ color: '#ffcf6a', transparent: true, opacity: 0, depthWrite: false });
  const rings = [0, 1, 2].map(() => { const r = new THREE.Mesh(new THREE.TorusGeometry(K.BELL_RIM_R, 0.0028, 8, 64), ringMat.clone()); r.rotation.y = Math.PI / 2; r.visible = false; T.group.add(r); return r; });

  const camera = new THREE.PerspectiveCamera(32, 1, 0.05, 20);
  const target = new THREE.Vector3(0.52, 1.22, 0);
  const VIEWS = { angle: { yaw: 0.75, pitch: 0.12, dist: 3.0 }, side: { yaw: 1.5708, pitch: 0.05, dist: 2.9 }, front: { yaw: 0.35, pitch: 0.1, dist: 2.9 } };
  const view = { ...VIEWS.angle };
  const placeCamera = () => {
    camera.position.set(target.x + view.dist * Math.cos(view.pitch) * Math.cos(view.yaw) * 0.999 + 0.001,
      target.y + view.dist * Math.sin(view.pitch), target.z + view.dist * Math.cos(view.pitch) * Math.sin(view.yaw));
    camera.lookAt(target);
  };
  placeCamera();

  // Orbit by drag, zoom by wheel/pinch (no external controls library).
  const pointers = new Map(); let pinch = 0;
  canvas.addEventListener('pointerdown', (e) => { canvas.setPointerCapture(e.pointerId); pointers.set(e.pointerId, [e.clientX, e.clientY]); });
  canvas.addEventListener('pointermove', (e) => {
    const p = pointers.get(e.pointerId); if (!p) return;
    if (pointers.size === 1) {
      view.yaw += (e.clientX - p[0]) * 0.008; view.pitch = Math.max(-0.15, Math.min(0.9, view.pitch + (e.clientY - p[1]) * 0.006));
    } else if (pointers.size === 2) {
      pointers.set(e.pointerId, [e.clientX, e.clientY]);
      const [a, b] = [...pointers.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (pinch) view.dist = Math.max(1.2, Math.min(4, view.dist * pinch / d)); pinch = d; return;
    }
    pointers.set(e.pointerId, [e.clientX, e.clientY]); placeCamera(); api.onViewChange?.();
  });
  const up = (e) => { pointers.delete(e.pointerId); if (pointers.size < 2) pinch = 0; };
  canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', up);
  canvas.addEventListener('wheel', (e) => { e.preventDefault(); view.dist = Math.max(1.2, Math.min(4, view.dist * (1 + Math.sign(e.deltaY) * 0.08))); placeCamera(); }, { passive: false });

  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const state = { ext: 0, from: 0, to: 0, t0: 0, dur: 0, sounding: 0, ringT: 0, ringIdx: 0, running: false, last: 0, size: [0, 0] };
  const tmp = { rs: new THREE.Vector3(), re: new THREE.Vector3(), rw: new THREE.Vector3(), rg: new THREE.Vector3() };
  const barRight = new THREE.Vector3(), barLeft = new THREE.Vector3();

  function pose(time) {
    const s = K.solvePose(state.ext), U = P.toUpper;
    const reach = K.reachFactor(state.ext);
    P.chest.rotation.y = s.twist * 0.6;             // the jacket follows most of the shoulder turn
    P.upper.rotation.z = -0.05 * reach;             // lean into sixth and seventh
    const breathe = reduced.matches ? 0 : Math.sin(time * 1.6) * 0.004;
    P.chest.scale.set(1 + breathe, 1, 1 + breathe);
    for (const [arm, sh, el, wr, grip, bar] of [
      [P.right, s.rightShoulder, s.rightElbow, s.rightWrist, s.rightGrip, barRight],
      [P.left, s.leftShoulder, s.leftElbow, s.leftWrist, s.leftGrip, barLeft]]) {
      tmp.rs.fromArray(U(sh)); tmp.re.fromArray(U(el)); tmp.rw.fromArray(U(wr)); tmp.rg.fromArray(U(grip));
      arm.shoulder.position.copy(tmp.rs); arm.elbow.position.copy(tmp.re);
      placeSegment(arm.upper, tmp.rs, tmp.re); placeSegment(arm.fore, tmp.re, tmp.rw);
      orientHand(arm.hand, tmp.rw, tmp.rg, bar);
    }
    T.outer.position.x = state.ext;
  }
  // Bars the hands close around, in upper-body space (instrument frame rotated by the slide pitch).
  const pitchQ = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), -K.SLIDE_PITCH);
  barRight.set(0, K.TUBE_B[0] - K.TUBE_A[0], K.TUBE_B[1] - K.TUBE_A[1]).normalize().applyQuaternion(pitchQ);
  barLeft.set(-1, 0, 0).applyQuaternion(pitchQ);        // left fingers wrap the slide from its left side

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h || (w === state.size[0] && h === state.size[1])) return;
    state.size = [w, h]; renderer.setSize(w, h, false); camera.aspect = w / h;
    camera.fov = w / h < 1 ? 42 : 32; camera.updateProjectionMatrix();
  }
  function frame(now) {
    if (!state.running) return;
    const t = now / 1000, dt = Math.min(0.1, t - (state.last || t)); state.last = t;
    if (state.dur > 0) {
      const u = (t - state.t0) / state.dur;
      state.ext = u >= 1 ? state.to : state.from + (state.to - state.from) * K.minJerk(u);
      if (u >= 1) state.dur = 0;
    }
    // Rings travel out of the bell while a note sounds.
    if (state.sounding > t && !reduced.matches) {
      state.ringT += dt;
      if (state.ringT > 0.22) { state.ringT = 0; const r = rings[state.ringIdx++ % rings.length]; r.userData.born = t; r.visible = true; }
    }
    for (const r of rings) {
      if (!r.visible) continue;
      const age = t - r.userData.born;
      if (age > 0.7) { r.visible = false; continue; }
      r.position.set(K.BELL_RIM_X + 0.02 + age * 0.35, K.BELL_AXIS[0], K.BELL_AXIS[1]);
      r.scale.setScalar(1 + age * 0.9); r.material.opacity = 0.55 * (1 - age / 0.7);
    }
    resize(); pose(t); renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }

  const api = {
    /** Move the slide to a position (1–7). Returns the target extension in metres, or null. */
    setPosition(position, { immediate = false } = {}) {
      const p = K.parsePosition(position); if (p == null) return null;
      const to = K.extensionFor(p);
      if (Math.abs(to - state.to) < 1e-6 && !immediate) return to;
      const now = performance.now() / 1000;
      state.from = state.ext; state.to = to; state.t0 = now;
      state.dur = immediate || reduced.matches ? 0 : K.moveDuration(state.ext, to);
      if (!state.dur) state.ext = to;
      return to;
    },
    /** Show sound leaving the bell for `seconds`. */
    sound(seconds) { state.sounding = Math.max(state.sounding, performance.now() / 1000 + Math.max(0.1, seconds)); },
    silence() { state.sounding = 0; },
    setView(name, look) { if (VIEWS[name]) { Object.assign(view, VIEWS[name], look?.view); if (look?.target) target.fromArray(look.target); placeCamera(); } },
    start() { if (!state.running) { state.running = true; state.last = 0; requestAnimationFrame(frame); } },
    stop() { state.running = false; },
    get extension() { return state.ext; },
    dispose() {
      state.running = false;
      scene.traverse((o) => { o.geometry?.dispose(); if (o.material) [].concat(o.material).forEach((m) => m.dispose()); });
      scene.environment?.dispose(); renderer.dispose();
    },
  };
  resize(); pose(0); renderer.render(scene, camera);
  return api;
}
