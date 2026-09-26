# Reader conductor

The reader's ▶ playback can show a conductor beside the metronome (button with the baton icon, key <kbd>C</kbd>).
While playing, a small panel under the toolbar draws the beat pattern (in 1 / in 2 / in 3 / in 4 / in 6),
moves the baton tip on the same audio clock as the metronome, shows the beat count, the conducting
tempo, and warns a few seconds ahead when the pattern changes (for example `▸ 75小節から in 1`).

## How the pattern is chosen

`public/reader/conductor.mjs` picks one pattern per bar, in this order:

1. **Forced** — the settings choice “いつも in N”, when N fits the bar (divides or subdivides the metronome beats).
2. **Plan** — the part's `conduct` entries (`[bar, beats per bar]`) in `project/**/dynamic/part.json`, copied into
   the reader data by `tools/dynamic/build_reader.py` (also by `--refresh-metadata`, which needs no source PDF).
3. **Auto** — an estimate from the meter and the score tempo (not the practice-tempo slider): 2/4 at ♩ ≥ 120 → in 1,
   ♩ < 56 → in 4; 3/4 at ♩ ≥ 144 → in 1; 3/8 at ♪ ≥ 144 → in 1; 4/4 and 2/2 at ♩ ≥ 132 → in 2; 6/8 at ♪ ≥ 132 → in 2.

A plan must carry `conduct_note`; `tools/dynamic/validate_reader.py` rejects a plan without one.
Conducting plans are practice guides chosen from the tempo marks and meter — they are not score readings,
not audit evidence, and conductors differ. Irregular meters (5/8, 7/8) are shown one beat per bar.

The panel shows the conductor's view by default: in 4, beat 1 is down, beat 2 left, beat 3 right,
and beat 4 up at the centre. “奏者の側から見た向き” mirrors the left and right positions.

## Current plans

| Part | Movement | Plan |
| --- | --- | --- |
| dvorak8-trombone1 | I (4/4) | in 2 at ♩=138 (1–126, 143–238, 251–); in 4 at ♩=112 (127–142, 239–250) |
| dvorak8-trombone1 | IV (2/4) | in 2 (1–74, 93–338); in 1 at ♩=126/144 (75–92, 339–) |

Other parts use the automatic estimate until a plan is added.
