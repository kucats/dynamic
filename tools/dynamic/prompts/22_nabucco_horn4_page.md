# Task: transcribe ONE page of a horn part (Verdi, Nabucco — Corno IV, whole opera) — pitch, rhythm, bars

Working dir: the repository root. Your page image: work/pPAGE.png (355 dpi grayscale, ~3520x4620 px;
PAGE = 100 + physical PDF page number).

Tools:
- `python3 tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png (left/right halves of system SYS,
  1-based from top). `python3 tools/dynamic/zoom.py PAGE SYS X0 X1 OUT.png` -> custom x range (~500–800 px close-ups).
  Pitch guides on the left: treble names (red/green), (bass) in grey, [alto] in purple — each tick is exactly at
  that line/space height. A blue x-ruler in PAGE pixel coordinates is at the top. Candidate noteheads from
  work/cand_pPAGE.json are circled — weak hints only (this engraving is poorly detected); find every notehead yourself.
- `python3 tools/dynamic/check.py PAGE` draws your notes on the page (work/chk_pPAGE_*.png).
- `python3 tools/dynamic/check_rhythm.py PAGE` checks durations/offsets against the meter.
- `python3 tools/dynamic/make_bars_auto.py PAGE` drafts work/bars_auto_pPAGE.json (barline detection + label guess);
  `python3 tools/dynamic/bars_overlay.py PAGE [work/bars_pPAGE.json]` draws the segments for checking.

## Reading rules (important)
- The part is printed in **treble clef** (horn). **Old-notation bass clef** may appear for low passages — it reads
  ONE OCTAVE LOWER than modern bass clef; judge by the natural-harmonic flow and mark such notes
  `"clef":"F","notation":"old-bass-clef"` (still report the pitch as printed).
- Horn parts have **no key signature** (accidentals are written out) — but check the clef area of every system anyway.
  An accidental lasts until the end of the bar on the same staff position, carries over a tie into the next bar,
  and is cancelled by a natural. Be extremely careful with every ♭, ♯ and ♮.
- **Crook changes** ("in Re", "in Mi♭", "muta in …") appear at movement headings and mid-flow — record each in
  meta.transpositions with the page-local bar where it takes effect.
- **Measure-repeat signs** (a slash with two dots) are frequent. For every such bar output the notes of the
  repeated bar again with `"sim": true`, same pitch/dur/off, `y` = the staff's middle line, `x` spread evenly
  inside that bar in onset order.
- EXCLUDE cue notes (small noteheads labelled with another instrument or sung text, usually with a rest in the
  same bar) and handwritten pencilled annotations — report their presence in issues instead.
- Use scientific octaves (C4 = middle C; treble bottom line = E4).
- **Bar numbers**: this edition prints NO bar numbers (boxed digits are rehearsal marks — record them in
  meta.rehearsal as {"bar": local, "mark": "3"}). Use PAGE-LOCAL numbering: count bars on your page starting at 1,
  continuing through movement boundaries without resetting; multi-bar rests count their full length (a printed
  "18" rest = 18 bars) and are labelled "a–b"; measure-repeat bars count as bars. The orchestrator adds offsets.
- If your page **begins mid-bar** (a bar split across the page end, e.g. a tie in), that first segment gets local
  bar **0** and is not counted in local_bar_count; set meta.continues_from_prev=true. If your page **ends
  mid-bar**, set meta.continues_to_next=true.
- Movement/section headings (SINFONIA, ATTO I CORO D'INTRODUZIONE, RECITATIVO…, "Coro", Tacet, …) define the
  musical numbers. Record each heading on your page in movements with its position {"sys","x"}; for a continued
  number report nothing.

## Output: work/final_pPAGE.json
{"page":PAGE,
 "movements":[{"mvt":"<printed heading>","starts_at":{"sys":S,"x":X}}],
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#4","clef":"G","bar":25,
           "dur":"1/4","off":"1/2","tie_from_prev":false,"sim":false,"uncertain":""}, ...],
 "meta":{"bars":[first_local,last_local],
         "meters":[{"bar":1,"meter":"4/4"}], "tempos":[{"bar":1,"text":"Andante","mm":""}],
         "transpositions":[{"bar":1,"text":"in Re"}],
         "rehearsal":[{"bar":1,"mark":"1"}],
         "local_bar_count": N, "continues_from_prev":false, "continues_to_next":false,
         "repeats":"free text", "movement_last_bar":{}}}
- One entry per played notehead in reading order; x,y = notehead centre in PAGE pixels (±10 px).
- dur/off are fractions of a whole note (triplet eighth = "1/12", grace = "0"); off = onset from the bar start.
- Include the meter in force at the top of the page even if not reprinted (C = 4/4, ¢ = 2/2).
- Movement boundaries: when a new number starts on your page, notes after its heading belong to it — keep counting
  page-local bars continuously; the orchestrator resets per movement using the boundary you report in movements[].
  If the boundary is inside a bar you cannot see, flag it in uncertain/issues.

## Then: bar numbers for every bar
work/bars_auto_pPAGE.json lists detected barline segments per system ({"xa","xb","label"}). Write
work/bars_pPAGE.json in the same structure with CORRECT page-local labels: fix false/missed barlines (stems are
often detected as barlines), label every segment, multi-bar rests as "a–b", a page-start continuation "0".
Every note must fall inside the segment carrying its bar number. Verify with bars_overlay.py and check_rhythm.py.

Reply briefly: note count, movement headings found, meters/tempos/transpositions, uncertain items.
Do not edit any files outside work/.
