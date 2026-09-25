# 3D trombone player (reader add-on)

A toy for trombone parts in `public/reader/`: a **3D** button opens a small panel with a
Three.js trombonist whose slide and right arm follow the selected note's position, ♪/←/→,
long-tone practice and ▶ playback (the slide leaves 90 ms early so it lands on the note).

## Add-on boundary

- `trombone3d-addon.js` (classic script, ~4 KB) is the only file the reader page loads. It adds the
  button for trombone parts and does nothing else until pressed. Pressing it fetches
  `trombone3d.css`, `trombone3d.js`, `trombone-motion.js` and the vendored Three.js
  (`vendor/three/`, MIT, r183). Nothing is remembered between visits.
- It talks to the reader only through `__dynamic.ext.addNoteHook(fn)`, called with
  `('select', {note})`, `('sound', {note, delayMs, seconds})` and `('silence')`.
- To remove the feature: delete the `trombone3d-addon.js` script tag in `public/reader/index.html`
  and the `trombone3d*`, `trombone-motion.js`, `vendor/three/` and `tests/reader/` files. The hook in
  `app.js` is generic and can stay.

## Model

- Positions come only from the reader data (`notes[].pos`); nothing is inferred from pitch.
- Slide distance: ideal B♭ tenor length 2.74 m, `2.74 / 2 · (2^((p−1)/12) − 1)` (≈ 57 cm to seventh).
  Bell rim between third and fourth; constant-length arm bones; torso turn and shoulder reach
  after fifth. The head is a plain ball on purpose.
- Tests: `node --test tests/reader/*.test.mjs`.

Ported from the Slide Studio prototype (kucats/karoakeProducer PR #20, issue #19); the player was
rebuilt rather than copied.
