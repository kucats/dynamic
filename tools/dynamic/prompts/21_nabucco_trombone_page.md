# Task: transcribe ONE page of a trombone part (Verdi, Nabucco — Sinfonia, Trombone 2) — pitch, rhythm, bars

Working dir: the repository root. Your page image: work/pPAGE.png (355 dpi grayscale, ~3520x4620 px).
(PAGE 202–204 = PDF pages 2–4 of the Nabucco Trombone 2 part: the Sinfonia.)

Tools:
- `python3 tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png (left/right halves of system SYS, 1-based from top).
  `python3 tools/dynamic/zoom.py PAGE SYS X0 X1 OUT.png` -> custom x range (use ~500–800 px wide close-ups).
  Pitch guides on the left: treble names (red/green), (bass) in grey, **[alto] in purple** — each tick is exactly at that
  line/space height. A blue x-ruler in PAGE pixel coordinates is at the top. Candidate noteheads from work/cand_pPAGE.json are
  circled — they are only weak hints (this engraving is poorly detected); find every notehead yourself.
- `python3 tools/dynamic/check.py PAGE` draws your notes on the page (work/chk_pPAGE_*.png).
- `python3 tools/dynamic/check_rhythm.py PAGE` checks durations/offsets against the meter.

## Reading rules (important)
- The part is printed in **bass clef** (tenor trombone). Watch for any clef change (tenor clef = C clef on the 4th line).
- **Key signatures change often** in this Sinfonia (e.g. 2 sharps, 3 sharps, 1 flat, naturals cancelling). Read the key signature at the
  start of EVERY system and at every double barline, and apply it to every note of that letter in all octaves. Apply accidentals
  within the bar and across ties. Be extremely careful with **B / B♭ / H(=B natural) and every ♯** — the user specifically asked for this.
- **Measure-repeat signs** (a slash with two dots, "repeat the previous bar", sometimes numbered 1 2 3… above) are frequent.
  For every such bar, output the notes of the repeated bar again with `"sim": true`, same pitch/dur/off, `y` = the staff's
  middle line, and `x` spread evenly inside that bar (in onset order) so each can be shown under the sign.
- EXCLUDE cue notes (small noteheads, often labelled with another instrument such as "Tr.ne I", with a rest in the same bar).
- Trombone is not transposing: the written pitch IS concert pitch. Use scientific octaves (C4 = middle C; bass clef top line = A3).
- **Bar numbers**: the part has no printed bar numbers. Use PAGE-LOCAL numbering: the first bar on your page is 1, multi-bar rests
  count their full length (a "15" rest = 15 bars), repeat-sign bars count as bars. The main agent adds the page offsets afterwards.
  If a bar is split across the page end (tie into the next page), say so.

## Output: work/final_pPAGE.json
{"page":PAGE,
 "movements":[{"mvt":"Sinfonia","starts_at":{"sys":S,"x":X}}],   // only if the Sinfonia heading is on this page
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#3","clef":"bass|tenor","bar":25,
           "dur":"1/4","off":"1/2","tie_from_prev":false,"sim":false,"uncertain":""}, ...],
 "meta":{"bars":[first,last] or {"I":[a,b],"IV":[c,d]},
         "meters":[{"bar":1,"meter":"4/4"}], "tempos":[{"bar":1,"text":"Andante","mm":""}], "local_bar_count": N,
         "key_signatures":[{"bar":1,"key":"2 sharps"}],
         "repeats":"free text: repeat barlines, 1st/2nd endings, D.S./Coda, fermatas", "movement_last_bar":{"I":355}}}
- One entry per played notehead in reading order; x,y = notehead centre in PAGE pixels (±10 px).
- dur/off as fractions of a whole note (triplet eighth = "1/12", grace = "0"); off = onset from the start of the bar.
- Include the meter in force at the top of the page even if not reprinted there (C = 4/4, ¢ = 2/2).
- local_bar_count = total bars on your page (for the page offsets).
- Record rehearsal marks (boxed letters A, B, …) with their page-local bar in meta.rehearsal.

## Then: bar numbers for every bar
work/bars_auto_pPAGE.json lists detected barline segments per system ({"xa","xb","label"}); view them with
`python3 tools/dynamic/bars_overlay.py PAGE` (work/barsov_pPAGE_*.png). Write work/bars_pPAGE.json with the same structure,
fixing false/missed barlines (stems are often detected as barlines) and giving every segment its printed bar number, multi-bar
rests as ranges "61–64" (en dash), using the same PAGE-LOCAL numbers. Every note you listed must fall inside the segment carrying its bar number.
Verify with `python3 tools/dynamic/bars_overlay.py PAGE work/bars_pPAGE.json`.

Reply briefly: note count, movements, meters/tempos/key signatures, clef changes, repeats, and any uncertain items.
Do not edit any other files.
