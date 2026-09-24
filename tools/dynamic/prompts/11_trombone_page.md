# Task: transcribe ONE page of a trombone part (Dvořák Symphony No. 8, Trombone I) — pitch AND rhythm

Working dir: the repository root. Your page image: work/pPAGE.png (340 dpi grayscale, ~3230x4250 px).
(PAGE 101–105 = PDF pages 1–5 of "Trombone_1_23Tuba.pdf"; the Trombone I part only.)

Tools:
- `python3 tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png (left/right halves of system SYS, 1-based from top).
  `python3 tools/dynamic/zoom.py PAGE SYS X0 X1 OUT.png` -> custom x range (use ~500–800 px wide close-ups).
  Pitch guides on the left: treble names (red/green), (bass) in grey, **[alto] in purple** — each tick is exactly at that
  line/space height. A blue x-ruler in PAGE pixel coordinates is at the top. Candidate noteheads from work/cand_pPAGE.json are
  circled — they are only weak hints (this engraving is poorly detected); find every notehead yourself.
- `python3 tools/dynamic/check.py PAGE` draws your notes on the page (work/chk_pPAGE_*.png).
- `python3 tools/dynamic/check_rhythm.py PAGE` checks durations/offsets against the meter.

## Reading rules (important)
- The part is mostly in **alto clef** (C clef centred on the MIDDLE line = C4). Watch for clef changes (bass clef, tenor clef
  = C clef on the 4th line, treble). Report the clef per note.
- **Key signature**: read it at the start of every system (G major = one sharp = every F is F#). Apply it to every F in all
  octaves unless a natural cancels it (for the rest of that bar). Also apply accidentals within the bar and across ties.
  Double-check every B/Bb, F/F#, C/C# — the user specifically complained about dropped flats/sharps before.
- EXCLUDE cue notes (small noteheads, usually labelled with another instrument, often with a rest in the same bar).
- Trombone is not transposing: the written pitch IS concert pitch. Use scientific octaves (C4 = middle C).

## Output: work/final_pPAGE.json
{"page":PAGE,
 "movements":[{"mvt":"I|IV","starts_at":{"sys":S,"x":X}}],          // movement headings on this page (II & III are tacet)
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#3","clef":"alto|bass|tenor|treble","bar":25,
           "dur":"1/4","off":"1/2","tie_from_prev":false,"uncertain":""}, ...],
 "meta":{"bars":[first,last] or {"I":[a,b],"IV":[c,d]},
         "meters":[{"bar":1,"meter":"3/4","mvt":"I"}], "tempos":[{"bar":1,"text":"Allegro con brio","mm":"","mvt":"I"}],
         "key_signatures":[{"bar":1,"key":"1 sharp","mvt":"I"}],
         "repeats":"free text: repeat barlines, 1st/2nd endings, D.S./Coda, fermatas", "movement_last_bar":{"I":355}}}
- One entry per played notehead in reading order; x,y = notehead centre in PAGE pixels (±10 px).
- dur/off as fractions of a whole note (triplet eighth = "1/12", grace = "0"); off = onset from the start of the bar.
- Include the meter in force at the top of the page even if not reprinted there.
- bar = printed bar number (count carefully through multi-bar rests; verify against the printed numbers).

## Then: bar numbers for every bar
work/bars_auto_pPAGE.json lists detected barline segments per system ({"xa","xb","label"}); view them with
`python3 tools/dynamic/bars_overlay.py PAGE` (work/barsov_pPAGE_*.png). Write work/bars_pPAGE.json with the same structure,
fixing false/missed barlines (stems are often detected as barlines) and giving every segment its printed bar number, multi-bar
rests as ranges "61–64" (en dash). Every note you listed must fall inside the segment carrying its bar number.
Verify with `python3 tools/dynamic/bars_overlay.py PAGE work/bars_pPAGE.json`.

Reply briefly: note count, movements, meters/tempos/key signatures, clef changes, repeats, and any uncertain items.
Do not edit any other files.
