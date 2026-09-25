/* Measure identity is independent of page layout, zoom, and old free-position pins. */
const range = (label) => {
  const [lo, hi = lo] = String(label).split('–').map(Number);
  return Number.isInteger(lo) && lo >= 1 && Number.isInteger(hi) && hi >= lo ? [lo, hi] : null;
};
const validBar = (bar) => Number.isInteger(bar) && bar >= 1 && bar <= 9999;

export function resolveMemoAnchor(data, anchor) {
  if (!anchor || typeof anchor.mvt !== 'string') return null;
  // An explicit bar is authoritative: never silently move a missing bar to old x/y.
  if (validBar(anchor.bar)) return { mvt: anchor.mvt, bar: anchor.bar };
  if (anchor.bar != null) return null;
  const sy = data.systems.find((s) => s.mvt === anchor.mvt && s.page === anchor.page && s.sys === anchor.sys);
  if (!sy || !Number.isFinite(anchor.x)) return null;
  const seg = sy.segs.find(([xa, xb, label]) => label && anchor.x >= xa && anchor.x < xb);
  const r = seg && range(seg[2]);
  // A free pin in a multi-measure rest cannot identify one exact bar safely.
  return r && r[0] === r[1] ? { mvt: anchor.mvt, bar: r[0] } : null;
}

export function memoPosition(data, anchor) {
  const a = resolveMemoAnchor(data, anchor);
  if (!a) return null;
  for (const sy of data.systems) {
    if (sy.mvt !== a.mvt) continue;
    for (let segment = 0; segment < sy.segs.length; segment++) {
      const [xa, xb, label] = sy.segs[segment], r = label && range(label);
      if (r && a.bar >= r[0] && a.bar <= r[1]) return { s: sy.i, segment, x: (xa + xb) / 2, xa, xb, anchor: a };
    }
  }
  return null;
}
