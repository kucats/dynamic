# Task: transcribe ONE page of a brass part (Sibelius Karelia Suite, Op. 11 — Trombone I/II/III or Tuba) — pitch AND rhythm AND bars

Working dir: the repository root, branch `devin/decode-karelia-trombone`
(`git fetch origin devin/decode-karelia-trombone && git checkout devin/decode-karelia-trombone`).
Source PDF: `work/karelia-trombone.pdf` (8 pages, scanned, no text layer — NOT committed; it may already be
in work/ or attached to your prompt as a page image). Your page image is rendered at
**300 dpi grayscale** as `work/p{PAGE}.png` (~3000x3900 px) where PAGE = 100 + PDF page number.

Part mapping (combined trombone+tuba PDF):
- "Trombone I"   = PDF pages 1–2 -> `project/sibelius/karelia-suite/trombone-i/dynamic/pages/`
- "Trombone II"  = PDF pages 3–4 -> `project/sibelius/karelia-suite/trombone-ii/dynamic/pages/`
- "Trombone III" = PDF pages 5–6 -> `project/sibelius/karelia-suite/trombone-iii/dynamic/pages/`
- "Tuba"         = PDF pages 7–8 -> `project/sibelius/karelia-suite/tuba/dynamic/pages/`

Page layout per part: the FIRST page holds all of **I. Intermezzo** plus a "II. Ballade tacet." text
line (no notes/bars — do not create bars for it). The SECOND page holds all of **III. Alla marcia**
starting at a fresh movement heading. Bar numbering RESTARTS at 1 in each movement.

Tools (python3 = ~/venvs/dynamic/bin/python):
- `python3 tools/dynamic/cand.py PAGE` -> work/cand_pPAGE.json note-head candidates + work/ov_pPAGE.png
  overlay + work/systems_pPAGE.json detected staves. CHECK the overlay first: if a system is missed or
  doubled, fix `work/systems_pPAGE.json` ({"systems":[[top..bottom 5 line y's], ...]}) or use
  `python3 tools/dynamic/mkstaves.py PAGE y1 y2 ...` then rerun cand.py.
- `python3 tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png (left/right halves of
  system SYS, 1-based from top). `python3 tools/dynamic/zoom.py PAGE SYS X0 X1 OUT.png` for custom
  x-range close-ups (~500-800 px). Pitch guides on the left: treble names (red/green), (bass) grey,
  [alto] purple; a blue x-ruler in PAGE px at top. Candidate noteheads are circled — weak hints only;
  find every notehead yourself.
- `python3 tools/dynamic/check.py PAGE` draws work/final_pPAGE.json onto the page (work/chk_pPAGE_*.png).
- `python3 tools/dynamic/check_rhythm.py PAGE` checks dur/off vs the meter in work/final_pPAGE.json.
- `python3 tools/dynamic/bars_auto.py PAGE` -> work/bars_auto_pPAGE.json barline hints (UNRELIABLE —
  stems are detected as barlines; multi-rest spans may be missed).

Workflow: write work/final_pPAGE.json + work/bars_pPAGE.json, iterate until check.py/check_rhythm.py/
bars_overlay.py look right, THEN copy to the final notes_pPP.json / bars_pPP.json paths below
(PP = 2-digit PDF page number, e.g. PAGE 101 -> notes_p01.json).

## Reading rules (important)
- **Clefs**: mostly bass clef. Alla marcia switches sections to **alto/tenor C-clef** for Trombone I/II
  (and late in Trombone III); a treble-clef cue system exists too. Report the clef per note
  ("bass", "alto", "tenor", "treble"). A C clef centred on the MIDDLE line = alto (C4); on the 4th
  line = tenor. Watch for mid-system clef changes back to bass.
- **Key signatures**: read at EVERY system start, each rehearsal letter, and each double bar.
  mvt I = 3 flats (B♭/E♭/A♭), 2/4 "Moderato". mvt III starts with 2 sharps "Moderato" and changes key
  at rehearsal letter A (courtesy naturals cancel the sharps, then flats — count exactly how many).
  Apply key signature to all octaves; accidentals persist within the bar and carry over ties.
  Double-check every B/E♭, F/C♯, G♯ — dropped accidentals were a prior complaint.
- **Meters**: mvt I = 2/4, mvt III = 2/4 (verify — check for changes near letters). Record every meter
  in force in meta.meters, including the one in force at the top of the page.
- **Multi-bar rests**: thick black block + count digit. ONE segment per block labelled as an en-dash
  range ("1–13"). Multi-rest blocks are SPLIT at rehearsal letters and at repeat barlines.
- **Printed digits under/above the staff are per-passage counters, NOT absolute bar numbers**: rest
  bars carry sequential digits (1,2,3...) that RESTART at each rehearsal letter or rest passage — e.g.
  after letter A a "12" block rest followed by bars numbered 13,14,15,16 = a 16-bar rest after A.
  Use them only to count. Small italic bar numbers every 5 bars just left of barlines may also appear —
  use them as anchors if present. OUTPUT bars must be numbered continuously from 1 at each movement
  start. Count every bar including cue passages and repeat bars.
- **Cue notes EXCLUDED**: small noteheads labelled with another instrument: "Vcl." (cello), "Viola",
  "Fl.I Ob.", "Tr.I."/"Tromba I." (= TRUMPET I — Italian tromba is trumpet, NOT trombone!), and on
  Trombone II/III/Tuba pages also "Tromb.I" (= trombone 1 shown as a cue). Do NOT put cues in notes[].
  Barlines around cue-only spans still bound real bars — count them. List excluded cue passages in
  meta.repeats free text (e.g. "cue notes excluded: Tr.I bars 38–53").
- **Rehearsal letters** (A, B, C ... above staff) -> meta.rehearsal [{"mark":"A","bar":N}] with the
  ABSOLUTE (continuous) bar number the letter stands at.
- Tempo directions mid-system ("Meno.", "Un pochett. string.", "Più moderato", "Poco largamente")
  -> meta.tempos entries at their bar. The opening "Moderato." goes at bar 1.
- Trombone/tuba are not transposing: written pitch = sounding pitch. Scientific octaves (C4 = middle C;
  bass clef top line = A3, alto clef middle line = C4, tenor clef 4th line = C4).
- flag every doubtful note with "uncertain":"unc" (pitch, octave, accidental, duration, bar).
- Simile/measure-repeat signs (slash with dots): re-emit the repeated notes with "sim":true, spread x
  evenly inside the bar, y = staff middle line.

## Output: write BOTH files at the FINAL paths (not work/):
- `project/sibelius/karelia-suite/<part-dir>/dynamic/pages/notes_pPP.json`
- `project/sibelius/karelia-suite/<part-dir>/dynamic/pages/bars_pPP.json`

notes_pPP.json schema (copy model `project/dvorak/symphony-no-8/trombone-i/dynamic/pages/notes_p01.json`):
```
{"page": PAGE,   // the p1NN render number, e.g. PDF page 1 -> "page":101
 "movements":[{"mvt":"I|III","starts_at":{"sys":S,"x":X}}],   // heading(s) on this page
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#3","clef":"bass","bar":25,
           "dur":"1/4","off":"1/2","tie_from_prev":false,"uncertain":""}, ...],
 "meta":{"bars":{"I":[1,152]} or [first,last],
         "meters":[{"bar":1,"meter":"2/4","mvt":"I"}],
         "tempos":[{"bar":1,"text":"Moderato","mm":"","mvt":"I"}],
         "key_signatures":[{"bar":1,"key":"3 flats","mvt":"I"}],
         "rehearsal":[{"mark":"A","bar":23,"mvt":"I"}],
         "repeats":"free text: repeat barlines incl. the mvt III opening repeated rest block,
                    volta endings, cue passages excluded, fermatas, unusual things",
         "movement_last_bar":{"I":152}}}
```
- One entry per played notehead, reading order (top->bottom, left->right); x,y = head centre in
  PAGE px (±10). Chords = one entry per notehead (same off).
- dur/off = fractions of a whole note ("1","1/2","1/4","1/8","1/16","3/16","1/12" triplet 8th,"0" grace);
  off = onset within the bar. dur+off must fit the bar's meter (check_rhythm.py must pass; under-full
  bars are OK — it cannot see rests — but overfull/overlaps are errors).
- Rests produce NO notes entries — they only consume bars in the counting.

## Then: bar segments for every bar
`bars_auto.py` output is a hint only. Write bars_pPP.json as {"1":[{"xa":X,"xb":X,"label":"N" or
"N–M"},...], "2":[...]} keyed by system number string: every printed bar gets a segment; multi-bar rests
get one segment labelled with the range; a rest passage's numbered rest bars may share one segment per
bar. Barlines inside cue passages still bound real bars. Repeat barlines and first/second endings get
their own segments. Every note must fall inside the segment carrying its bar number.
Verify with `python3 tools/dynamic/bars_overlay.py PAGE work/bars_pPP.json`.

## Commit (last step)
`git add` ONLY the two JSON files; `git commit -m "karelia <part-dir> pPP notes+bars"`;
`git pull --rebase origin devin/decode-karelia-trombone`; `git push origin devin/decode-karelia-trombone`.
On a non-fast-forward reject, repeat pull --rebase + push (up to 5 tries — sibling pages push in
parallel). Never commit the PDF, renders, work/ files, or crops.

Reply briefly (structured output): page, part dir, committed/pushed, note count, bar range per
movement, movements/meters/tempos/key signatures seen, rehearsal letters, cue passages excluded,
uncertain count, issues list.
