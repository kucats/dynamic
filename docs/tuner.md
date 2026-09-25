# Tuner (reader add-on)

A microphone tuner for everyday practice in `public/reader/`. The **チューナー** button (top right, next to 説明)
is on every part and works whether or not anything is playing.

## Add-on boundary

- `tuner-addon.js` (classic script) is the only file the reader page loads. It adds the button and does nothing else
  until pressed. Pressing it fetches `tuner.css`, `tuner.mjs` and `tuner-pitch.mjs`, then asks for the microphone.
- The microphone is open only while the panel is open and not paused; closing the panel, pausing, or hiding the tab
  stops every track. Audio is analysed in the page and never stored or sent. Only the chosen A4 and the horn display
  mode are remembered (`localStorage` key `dynamic-tuner`).
- It does not read or change reader data, audit states, playback or memos. A tuner reading is not score evidence.
- To remove the feature: delete the `tuner-addon.js` script tag in `public/reader/index.html`, the `tuner*` files,
  the `.tuner-btn` rules in `app.css`, and `tests/reader/tuner-pitch.test.mjs`.

## Model

- Pitch: YIN on a 4096-sample window (sample rates of 32 kHz or more are halved first), searching 50–1400 Hz,
  about 20 times a second. The median of the last five detections is shown; the cents value is smoothed within a
  note and resets on a note change.
- Display: ±50 cents gauge; green within ±5, amber within ±15. The strip below shows the last 6 seconds.
  A4 = 436–446 Hz (default 442).
- Names follow the reader: trombone parts use the German letters of the parts (B♭, H), horn parts fixed ドレミ with
  a 実音 / F管読み (a perfect fifth above the sounding pitch) switch. English letter names are shown underneath.
- Tests: `node --test tests/reader/tuner-pitch.test.mjs`.
