# Task: transcribe ONE page of a flute-family part (Sibelius Karelia Suite, Op. 11) — pitch AND rhythm

Working dir: the repository root, branch `devin/decode-karelia-flute`.
Source PDF: `work/karelia-flute.pdf` (8 pages, scanned, no text layer). Your page image is rendered at
**340 dpi grayscale** as `work/p{100+N}.png` (~3400x4420 px) where N = PDF page number (1..8).

Part mapping:
- "Flauto I"   = PDF pages 1–3 -> `project/sibelius/karelia-suite/flute-i/dynamic/pages/`
- "Flauto II"  = PDF pages 4–6 -> `project/sibelius/karelia-suite/flute-ii/dynamic/pages/`
- "Flauto piccolo" = PDF pages 7–8 -> `project/sibelius/karelia-suite/piccolo/dynamic/pages/`

Movements (Karelia Suite): **I. Intermezzo** ("Moderato"), **II. Ballade** (flutes+piccolo TACET — a
"Ballade tacet." text line only, no notes/bars), **III. Alla marcia**. Page 1 of each part holds all of
Intermezzo; Alla marcia starts at the top of the next page with a fresh movement heading AND a new
key signature + time signature. Bar numbering RESTARTS at 1 in each movement (verify against printed
bar numbers).

Tools (python3 = ~/venvs/dynamic/bin/python):
- `python3 tools/dynamic/mkstaves.py PAGE y1 y2 ...` -> `work/staves_pPAGE.json` staff override
  (REQUIRED — the orchestration detector mis-segments these pages; y_i = top-line y per system,
  supplied per page in your task). Then `cand.py`/`zoom.py`/`bars_auto.py`/`bars_overlay.py` pick it up.
- `python3 tools/dynamic/cand.py PAGE` -> work/cand_pPAGE.json note-head candidates + work/ov_pPAGE.png overlay.
- `python3 tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png (left/right halves of
  system SYS, 1-based from top). `python3 tools/dynamic/zoom.py PAGE SYS X0 X1 OUT.png` for a custom
  x range (~500-800 px close-ups; cands confuse stems/flags).
  Pitch guides on the left: treble names (red/green); a blue x-ruler in PAGE px at top. Candidate
  noteheads are circled with cid — weak hints only; find every notehead yourself.
- `python3 tools/dynamic/check.py PAGE` draws work/final_pPAGE.json onto the page (work/chk_pPAGE_*.png).
- `python3 tools/dynamic/check_rhythm.py PAGE` checks dur/off vs the meter in work/final_pPAGE.json.
- `python3 tools/dynamic/bars_auto.py PAGE` -> work/bars_auto_pPAGE.json barline hints (UNRELIABLE).

Workflow: write work/final_pPAGE.json + work/bars_pPAGE.json, iterate until check.py/check_rhythm.py/
bars_overlay.py look right, THEN copy to the final notes_pPP.json / bars_pPP.json paths below.

## Reading rules (important)
- Clef: treble ("G") for all played notes. Cue notes may switch clef — they are excluded anyway.
- **Key signatures**: read at every system start AND at each movement heading.
  Flauto I/II: mvt I = 2 flats (B♭/E♭), mvt III = sharps (count them — appears to be 3: F♯/C♯/G♯).
  Flauto piccolo: mvt I shows sharps (verify count — may differ from flute I).
  Apply to all octaves until cancelled by a natural (rest of that bar) or next bar. Accidentals
  persist within a bar and carry over ties. Double-check every B/E♭, F/C♯, G♯.
- **Meters**: mvt I = 2/4; mvt III = 2/4 (a possible meter change mid-movement has been seen —
  check near rehearsal letters). Record every meter in force in meta.meters (include the one at
  page top even when mid-movement).
- **Multi-bar rests**: thick black block + count digit ("1","2","4","5","6","7","13","16","21","22"...).
  The block = N consecutive rest bars = ONE segment labelled as a range ("61–64", en dash).
  Multi-bar rests are SPLIT at rehearsal letters: a letter above starts a new segment.
- **Cue notes EXCLUDED**: small noteheads labelled with another instrument ("Tr.I.", "Viola",
  "Clar.", "Corn."...), often with a small clef/dynamic; they may be beamed eighths running across
  several bars while the flute part shows rests. Do NOT put cues in notes[]. The barlines around
  cue-only spans are still real barlines — count those bars. List excluded cue passages in
  meta.repeats free text (e.g. "Cue notes excluded: Tr.I. bars 53–57, Viola 79–100").
- **Printed bar numbers**: small italic digits every 5 bars just LEFT of the barline where the
  numbered bar starts. Use as anchors; count between them.
- Rehearsal letters (A, B, C ... above staff) -> meta.rehearsal [{"mark":"A","bar":N}].
  Tempo directions mid-system ("Meno.", "Un pochett. string.", "Più moderato", "Poco largamente")
  -> meta.tempos entries at their bar.
- Written pitch = sounding pitch for flute; piccolo sounds an octave up but write AS PRINTED
  (treble staff position). Scientific octaves, C4 = middle C.
- flag every doubtful note with "uncertain":"unc" (pitch, octave, accidental, duration, bar).

## Output: write BOTH files at the FINAL paths (not work/):
- `project/sibelius/karelia-suite/<part-dir>/dynamic/pages/notes_pPP.json`   (PP = 2-digit PDF page)
- `project/sibelius/karelia-suite/<part-dir>/dynamic/pages/bars_pPP.json`

notes_pPP.json schema (copy model `project/dvorak/symphony-no-8/trombone-i/dynamic/pages/notes_p01.json`):
```
{"page": 100+PP,   // e.g. PDF page 1 -> "page":101  (the p1NN render number, per trombone-i precedent)
 "movements":[{"mvt":"I|III","starts_at":{"sys":S,"x":X}}],
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#5","clef":"G","bar":25,
           "dur":"1/4","off":"1/2","tie_from_prev":false,"uncertain":""}, ...],
 "meta":{"bars":{"I":[1,134]} or [first,last],
         "meters":[{"bar":1,"meter":"2/4","mvt":"I"}],
         "tempos":[{"bar":1,"text":"Moderato","mm":"","mvt":"I"}],
         "key_signatures":[{"bar":1,"key":"2 flats","mvt":"I"}],
         "rehearsal":[{"mark":"A","bar":23}],
         "repeats":"free text: cue passages excluded, fermatas, anything unusual",
         "movement_last_bar":{"I":134}}}
```
- One entry per played notehead, reading order (top->bottom, left->right); x,y = head centre in
  PAGE px (±10). Chords = one entry per notehead (same off).
- dur/off = fractions of a whole note ("1","1/2","1/4","1/8","1/16","1/12" triplet 8th,"0" grace);
  off = onset within the bar. dur+off must fit the bar's meter (check_rhythm.py must pass).
- Simile/measure-repeat signs: re-emit repeated notes with "sim":true.
- Rests produce NO notes entries — they only consume bars in the counting.

## Then: bar segments for every bar
`bars_auto.py` output is a hint only — it misses multi-rest boundaries and flags stems as barlines.
Write bars_pPP.json as {"1":[{"xa":X,"xb":X,"label":"N" or "N–M"},...], "2":[...]} keyed by system
number string: every printed bar gets a segment; multi-bar rests get one segment labelled with the
range. Barlines inside cue passages still bound real bars. Every note must fall inside the segment
carrying its bar number. Verify with `python3 tools/dynamic/bars_overlay.py PAGE <bars path>`.

## Commit (last step)
`git add` ONLY the two JSON files; `git commit -m "karelia <part-dir> pPP notes+bars"`;
`git pull --rebase origin devin/decode-karelia-flute`; `git push origin devin/decode-karelia-flute`.
On a non-fast-forward reject, repeat pull --rebase + push (up to 5 tries — sibling pages push
in parallel). Never commit the PDF, renders, work/ files, or crops.

Reply briefly (structured output): page, part dir, committed/pushed, note count, bar range per
movement, movements/meters/tempos/key signatures seen, rehearsal letters, cue passages excluded,
uncertain count, issues list.
