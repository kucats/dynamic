# Task: transcribe ONE page of a horn part (Verdi, Nabucco — Corno III) — pitch, rhythm, bars

Working dir: the repository root. Your page image: work/pPAGE.png (355 dpi grayscale, ~3520x4620 px).

Tools:
- `python3 tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png (left/right halves of system SYS, 1-based from top).
  `python3 tools/dynamic/zoom.py PAGE SYS X0 X1 OUT.png` -> custom x range (use ~500–800 px wide close-ups).
  Pitch guides on the left: treble names (red/green), (bass) in grey, [alto] in purple — each tick is exactly at that
  line/space height. A blue x-ruler in PAGE pixel coordinates is at the top. Candidate noteheads from work/cand_pPAGE.json are
  circled — they are only weak hints (this engraving is poorly detected); find every notehead yourself.
- `python3 tools/dynamic/check.py PAGE` draws your notes on the page (work/chk_pPAGE_*.png).
- `python3 tools/dynamic/check_rhythm.py PAGE` checks durations/offsets against the meter.
- `python3 tools/dynamic/bars_auto.py PAGE` builds work/bars_auto_pPAGE.json (needs your final_pPAGE.json first);
  `python3 tools/dynamic/bars_overlay.py PAGE` draws them (work/barsov_pPAGE_*.png).

## Reading rules (important)
- The part is **Corno III** (horn 3), printed mostly in **treble clef**. Old-notation **bass clef** may appear
  (horn old notation writes bass clef a fourth below sounding = one octave below modern reading);
  mark such notes `"clef": "F"`, `"notation": "old-bass-clef"`, and give the pitch as it literally reads in bass clef.
- **Horn transposition**: every number/section is headed "Corno III. in Do" / "in Re" / "in Mi♭" / "in Fa" / "muta in …" etc.
  Record EVERY such instruction in meta.transpositions with the local bar where it takes effect.
- Usually **no key signature** in horn parts — but check the clef area of EVERY system and at double barlines; if a key
  signature is printed, record it in meta.key_signatures and apply it to that letter in all octaves.
- Accidentals: ♭/♯/♮ last until the end of the bar for the same staff position, carry over a tie into the next bar,
  and are cancelled by a natural. Be extremely careful — dropped flats were a user complaint before.
- **Measure-repeat signs** (a slash with two dots, "repeat the previous bar", often numbered 1 2 3… above): for every such
  bar, output the notes of the repeated bar again with `"sim": true`, same pitch/dur/off, `y` = the staff's middle line,
  and `x` spread evenly inside that bar (in onset order) so each can be shown under the sign.
- **Cue notes** — small noteheads of other instruments or sung cue phrases (lyric text like "di mia ven-detta" under the
  staff), usually over a whole-bar rest — are NOT the horn's notes: EXCLUDE them. If genuinely ambiguous, include with a
  non-empty `uncertain` note (e.g. "could be cue").
- Written pitch in scientific notation (C4 = middle C; treble bottom line = E4), e.g. "F#4", "Eb5", "C4".
- **Bar numbering**: NO printed bar numbers. Number bars with PAGE-LOCAL counting: the first bar of each opera NUMBER's
  region on your page counts from 1 separately per number (i.e. count within each number's on-page region — a number that
  continues from a previous page still starts its on-page count at 1). Multi-bar rests count their full length
  (a printed "15" rest = 15 bars). Measure-repeat bars count as bars. Give every note `"bar"` = that local index and also
  `"mvt"` = the exact printed heading of its number (e.g. "SINFONIA", "CORO D'INTRODUZIONE", "FINALE SECONDO").
  The orchestrator adds the cross-page offsets afterwards.
- **Movements/numbers**: record in "movements" every number heading that STARTS on your page: {"mvt":"<printed heading>",
  "starts_at":{"sys":S,"x":X}, "local_start":<first local bar of that region on this page>}. A number marked "Tace"/"Tacet"
  gets {"tacet": true} and no notes; still record the heading.

## Output: work/final_pPAGE.json
{"page":PAGE,
 "movements":[{"mvt":"<printed heading>","starts_at":{"sys":S,"x":X},"local_start":1}],
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#4","clef":"G","mvt":"<heading>","bar":3,
           "dur":"1/4","off":"1/2","tie_from_prev":false,"sim":false,"uncertain":""}, ...],
 "meta":{"movement_bars":{"<heading>":[first_local,last_local], ...},
         "local_bar_count": N (per number is implicit in movement_bars; also give total bars on the page),
         "meters":[{"bar":1,"meter":"4/4","mvt":"<heading>"}], "tempos":[{"bar":1,"text":"Allegro","mm":"","mvt":"<heading>"}],
         "transpositions":[{"bar":1,"text":"in Do","mvt":"<heading>"}],
         "key_signatures":[{"bar":1,"key":"2 sharps","mvt":"<heading>"}],
         "rehearsal":[{"bar":5,"mark":"E","mvt":"<heading>"}],
         "repeats":"free text: repeat barlines, 1st/2nd endings, D.S./Coda, fermatas",
         "movement_last_bar":{"<heading>":N}  // only when a number ENDS on your page (final double bar)
        }}
- One entry per played notehead in reading order; x,y = notehead centre in PAGE pixels (±10 px).
- dur/off as fractions of a whole note (triplet eighth = "1/12", grace = "0"); off = onset from the start of the bar.
- Include the meter in force at the top of the page even if not reprinted there (C = 4/4, ¢ = 2/2).
- If a bar is split across the page end (tie into the next page), say so in meta.repeats or the report.

## Then: bar numbers for every bar
After writing final_pPAGE.json run `python3 tools/dynamic/bars_auto.py PAGE`, view with
`python3 tools/dynamic/bars_overlay.py PAGE` (work/barsov_pPAGE_*.png). Write work/bars_pPAGE.json with the same
{"sys":[{"xa","xb","label"}]} structure, fixing false/missed barlines (stems are often detected as barlines) and giving
every segment its LOCAL bar label within its number (same counting as your notes; multi-bar rests as ranges "61–64" en
dash). Where a new number starts mid-system, the boundary segment gets the new number's local "1". Every note must fall
inside the segment carrying its local bar number. Verify with `python3 tools/dynamic/bars_overlay.py PAGE work/bars_pPAGE.json`.

Reply briefly via structured output: note count, per-number local bar ranges, meters/tempos/transpositions, clef changes,
repeats, and any uncertain items. Do not edit any repository files outside work/.
