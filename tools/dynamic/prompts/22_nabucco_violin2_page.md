# Task: transcribe ONE page of a violin part (Verdi, Nabucco — Violin II) — pitch, rhythm, bars

Working dir: the repository root. Your page image: work/pPAGE.png (300 dpi grayscale, ~2967x3903 px).
The whole PDF is the Violin II part of the full opera (64 pages). Page = PDF page number.

Tools:
- `~/venvs/dynamic/bin/python tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png
  (left/right halves of system SYS, 1-based from top).
  `zoom.py PAGE SYS X0 X1 OUT.png` -> custom x range (use ~500–800 px wide close-ups).
  Pitch guides on the left: treble names (red/green), (bass) in grey, [alto] in purple — each tick is exactly
  at that line/space height. A blue x-ruler in PAGE pixel coordinates is at the top. Candidate noteheads from
  work/cand_pPAGE.json are circled — they are weak hints only; find every notehead yourself.
- `~/venvs/dynamic/bin/python tools/dynamic/check.py PAGE` draws your notes on the page (work/chk_pPAGE_*.png).
- `~/venvs/dynamic/bin/python tools/dynamic/check_rhythm.py PAGE` checks durations/offsets against the meter.
- `~/venvs/dynamic/bin/python tools/dynamic/mkbars.py PAGE` builds work/bars_auto_pPAGE.json from your
  final_pPAGE.json (run it only AFTER final_pPAGE.json exists with bar/dur/off filled).

## Reading rules (important)
- The part is **treble clef** throughout. Violin II is not transposing: written pitch = concert pitch,
  scientific octaves (C4 = middle C; treble bottom line = E4). Report clef "G".
- **Key signatures change often**. Read the key signature at the start of EVERY system and at every double
  barline / movement heading, and apply it to every note of that letter in all octaves. Accidentals persist
  within a bar and carry over ties; a natural cancels. Be extremely careful with ♭/♯/♮ — dropped accidentals
  were a problem in past runs.
- **Chords / double stops**: stacked noteheads sharing one stem are BOTH played — write one entry per
  notehead (same x, same bar/off/dur).
- **Divisi**: two rhythmic voices on one staff (stems up vs down) are both played — transcribe both voices.
- **Measure-repeat signs** (slash with two dots, sometimes numbered above): output the repeated bar's notes
  again with `"sim": true`, same pitch/dur/off, y = middle line, x spread evenly inside that bar.
- **Tremolo**: slashes across a stem mean measured repetition (e.g. a half note with 2 slashes = four 8ths).
  Write the repeated notes explicitly with `"sim": true`, same pitch, evenly spread x, correct off/dur.
- EXCLUDE cue notes (small noteheads, usually labelled with another instrument like "Vl.I", "Ob.", "Cl.",
  often with a rest in the same bar). Compare notehead size with clearly normal notes.
- Grace notes (small heads before the beat) ARE played: keep them with dur "0".
- pizz./arco/col legno/con sordino are playing techniques — do not transcribe them, but list them in
  meta.marks (with the local bar) since they matter to the reader.

## Bar numbers — page-local (the part prints NO bar numbers)
- Number bars page-locally: the first bar region on your page is 1; multi-bar rests count their full length
  (a "15" rest = 15 bars); repeat-sign and 1st/2nd-ending bars count as bars. The main agent adds page
  offsets afterwards, so NEVER try to guess global numbers.
- A bar can be split across the page boundary: set `first_bar_continues` true if the page begins inside a
  bar that started on the previous page (notes before the first barline of the top system with no opening
  barline), and `last_bar_split` true if the last bar continues onto the next page.
- If a printed bar number ever IS present (some editions print one every 5 bars), report the mapping in
  meta.printed_bars and still keep page-local numbering in note.bar.

## Movements / numbers
This score is an opera part: movements begin at headings like "SINFONIA", "Nº 2", "CORO", "RECITATIVO",
"SCENA", "ATTO ...", "FINALE", etc. — often mid-page. For every heading on your page put an entry in
"movements" with the heading text verbatim and {"sys":S,"x":X}. A movement start resets local bar counting
to 1 for the bars that follow it; use meta.bars as a per-movement map ({"Sinfonia":[a,b],"N3":[c,d]}) when
more than one movement shares the page, and pick short ASCII keys ("S", "N1", "N2", ...; for recitative
linked to a number use "N2r" style suffixes only if it is clearly a separate sub-section of that number).

## Output: work/final_pPAGE.json
{"page":PAGE,
 "movements":[{"mvt":"<heading text>","key":"S","starts_at":{"sys":S,"x":X}}],
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#4","clef":"G","bar":25,
           "dur":"1/4","off":"1/2","tie_from_prev":false,"sim":false,"uncertain":""}, ...],
 "meta":{"bars":[first,last] or {"S":[a,b],"N1":[c,d]},
         "meters":[{"bar":1,"meter":"4/4"}], "tempos":[{"bar":1,"text":"Andante","mm":""}],
         "local_bar_count": N,
         "first_bar_continues": false, "last_bar_split": false,
         "key_signatures":[{"bar":1,"key":"3 sharps"}],
         "rehearsal":[{"bar":53,"mark":"C"}],
         "marks":[{"bar":20,"text":"pizz."}],
         "repeats":"free text: repeat barlines, 1st/2nd endings, D.S./Coda/segno, fermatas",
         "printed_bars":[{"local":1,"printed":121}]}}
- One entry per played notehead in reading order (system by system, left to right; for chords list the
  noteheads together). x,y = notehead centre in PAGE pixels (±10 px). Rests produce no entries.
- dur/off are fractions of a whole note (triplet 8th = "1/12", grace = "0"); off = onset inside its bar.
  Double check off+dur of the last note never exceeds the bar length.
- bar = the page-local bar number, EVERY note must have it filled. Sim notes take the bar they sit in.
- Include the meter in force at the top of the page even if not reprinted there (C = 4/4, ¢ = 2/2).
- local_bar_count = total LOCAL bars on your page (counting split first/last bars once each).
- rehearsal = boxed letter marks (A, B, C, ...) with their local bar; marks = technique/section text.
- uncertain = "" or a short note (e.g. "could be cue", "pitch A5 or G5"). Flag anything unresolved.

## Then: bar numbers for every bar
Run `~/venvs/dynamic/bin/python tools/dynamic/mkbars.py PAGE` to build work/bars_auto_pPAGE.json, view it with
`~/venvs/dynamic/bin/python tools/dynamic/bars_overlay.py PAGE` (work/barsov_pPAGE_*.png). Write
work/bars_pPAGE.json with the same per-system structure but CORRECT labels:
- every segment gets its page-local bar number; a multi-bar rest segment gets a range "61–64" (en dash).
- Merge false "barlines" (stems are often detected), split segments where a real barline was missed.
- The first segment of each system starts at the system start; drop tiny trailing segments after the final
  barline. Every note you listed must fall inside the segment carrying its bar number.
- If a movement starts mid-system, the barline before it ends the previous movement's last bar; the segment
  after it is local bar 1 of the new movement.
Verify with `bars_overlay.py PAGE work/bars_pPAGE.json` and re-check the images.

## Verify before reporting
1. `check.py PAGE` — look at every chk image: no misplaced, missing, or extra noteheads; pitches sane.
2. `check_rhythm.py PAGE` — fix real errors it reports (overfull bars, overlaps). It cannot see rests, so a
   bar that is only partly filled by notes is fine.
3. `bars_overlay.py PAGE work/bars_pPAGE.json` — every segment labelled, every note inside its bar.

## Report (structured output)
Upload work/final_pPAGE.json and work/bars_pPAGE.json with the upload_attachment tool and return:
page, notes_url, bars_url, notes (count), bars (local count), uncertain (count), plus these text fields:
- movements: "heading@sysN,xNNN; ..." or ""
- meters: "localbar:meter; ..."   tempos: "localbar:TEXT(mm); ..."
- key_sigs: "localbar:key; ..."   rehearsal: "localbar:LETTER; ..."   marks: "localbar:text; ..."
- first_bar_continues, last_bar_split (true/false), bars_range: "firstlocal-lastlocal" per movement if split
- issues: anything unresolved (bad scan region, ambiguous reading, page anomalies)
Do not commit anything and do not edit any files outside work/.
