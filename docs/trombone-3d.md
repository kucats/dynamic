# 3D trombone player (DYNAMIC reader)

Trombone parts in `public/reader/` have a **3D奏者** toggle. When it is on, a panel shows a
procedural Three.js trombonist whose outer slide and right arm move to the slide position of the
selected note, the note sounded with ♪/←/→, the long-tone practice note, and each note during
▶ playback. During playback the slide starts moving 90 ms before the note so it arrives on time,
and faint rings leave the bell while a note sounds.

## Boundaries

- Positions come only from the reader data (`notes[].pos`). Nothing is inferred from pitch; a
  note without a position keeps the previous slide position.
- Slide distances use an ideal B♭ tenor length of 2.74 m (`extension = 2.74 / 2 · (2^((p−1)/12) − 1)`,
  about 57 cm from first to seventh). They are a visual guide, not an intonation chart; real
  positions vary with the instrument, register and tuning. F-attachment positions are not modelled.
- The setting is per viewer (`localStorage`), off by default, and hidden for horn parts and print
  pages. Three.js (`public/reader/vendor/three/`, MIT, r183) is fetched only after the toggle is
  switched on.

## Model

- `public/reader/trombone-motion.js` holds the geometry and kinematics without rendering:
  instrument landmarks (bell rim between third and fourth position, roughly 4 cm of inner slide left
  in the outer slide at seventh), a two-bone arm with constant segment lengths, a right wrist that
  hangs below the brace near the body and straightens into a fingertip grip at the far positions,
  and a torso turn plus shoulder-blade reach that start after fifth position.
- `public/reader/trombone3d.js` builds the player (suit, head with a firm embouchure, left hand
  holding the slide/bell braces, right hand on the slide brace) and the instrument (mouthpiece,
  nickel inner slide, rigid brass outer slide with water key, tuning slide over the left shoulder,
  flared bell). Slide changes use a minimum-jerk profile of 90–300 ms; reduced-motion snaps.
- Tests: `node --test tests/reader/*.test.mjs`.

## Origin

Ported from the Slide Studio prototype (kucats/karoakeProducer PR #20, issue #19). The practical
landmarks it used remain the reference:
[ODU Trombone Studio slide tips](https://fs.wp.odu.edu/jhall/performance-clinic/slide-tips/),
[Yamaha: how the slide works](https://www.yamaha.com/en/musical_instrument_guide/trombone/mechanism/mechanism002.html).
The prototype's figure, cue API and generated concept images were not copied; the player was rebuilt
with human proportions and a playing posture.
