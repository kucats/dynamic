# Task: transcribe ONE page of a flute part (Dvořák Symphony No. 8, Flauto I or Flauto II) — pitch AND rhythm

Working dir: the repository root. Your page image: work/pPAGE.png (300 dpi grayscale, ~2964x3900 px).
The printed part is a single-column orchestral part; the PDF page number IS your PAGE number.

- Flauto I = PDF pages 1–15  -> project/dvorak/symphony-no-8/flute-i/dynamic/pages/
- Flauto II (doubles piccolo, heading "FLAUTO II. (FLAUTO PICCOLO)") = PDF pages 16–26
  -> project/dvorak/symphony-no-8/flute-ii/dynamic/pages/

Tools (python3 = ~/venvs/dynamic/bin/python or repo blueprint python3):
- `python3 tools/dynamic/cand.py PAGE` -> work/cand_pPAGE.json note-head candidates + work/ov_pPAGE.png overlay.
- `python3 tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png (left/right halves of system SYS, 1-based from top).
  `python3 tools/dynamic/zoom.py PAGE SYS X0 X1 OUT.png` -> custom x range (use ~500–800 px wide close-ups; cands get confused by stems/flags).
  Pitch guides on the left: treble names (red/green), (bass) in grey — each tick is exactly at that line/space height.
  A blue x-ruler in PAGE pixel coordinates is at the top. Candidate noteheads are circled with their cid — they are
  only weak hints (this engraving detects many false heads and misses others); find every notehead yourself.
- `python3 tools/dynamic/check.py PAGE` draws your work/final_pPAGE.json notes on the page (work/chk_pPAGE_*.png).
- `python3 tools/dynamic/check_rhythm.py PAGE` checks durations/offsets in work/final_pPAGE.json against the meter.
- `python3 tools/dynamic/bars_auto.py PAGE` -> work/bars_auto_pPAGE.json auto barline segments (weak hints).

Workflow: first write work/final_pPAGE.json and work/bars_pPAGE.json, iterate until check.py/check_rhythm.py/
bars_overlay.py look right, THEN copy final_pPAGE.json -> notes path and bars_pPAGE.json -> bars path below.

## Reading rules (important)
- Clef: **treble ("G")** for all played notes. CUE notes may appear in bass clef — they are excluded anyway (below).
- **Key signature**: read it at the start of every system. Mvt I & IV = G major (1 sharp), mvt II = E♭ major (2 flats),
  mvt III = G minor (2 flats). Apply to every affected pitch in all octaves unless cancelled by a natural (rest of that bar).
  Apply accidentals within the bar and across ties into the next bar. Double-check every B/B♭, E♭/E♮, F/F♯, C/C♯.
- **Meters**: I = 4/4 ("C"), II = 2/4, III = 3/8 (changes to 2/4 at bar 181, "Molto vivace" Coda), IV = 2/4.
  Movement headings are printed mid-page where each movement starts.
- **Rhythm traps in this engraving**:
  - Eighth notes are FLAGGED individually (not beamed) when staccato — each flag is a small hook on the stem that
    looks almost exactly like an eighth rest. Do not confuse flags with rests; count stems.
  - Beamed groups do occur (16th runs). Staccato dots/accents/slurs are articulation, not rhythm.
  - Multi-bar rests: thick black horizontal block on the staff with a count digit above ("2","3","4","5","10"...).
    The whole block = N consecutive rest bars = ONE segment labelled as a range ("61–64", en dash).
  - Printed bar numbers (italic, every 5 bars: 5,10,15,20,25...) sit just LEFT of the barline where the numbered
    bar STARTS. Use them as anchors and count between them.
- **Cue notes EXCLUDED**: small noteheads labelled with another instrument ("Trbni I,II.", "Viol.I", "Ob.I", "Fag.",
  "Fl.I", "Fl.II", "Timp."...), often with a clef change to bass and a "pp"/"ppp" dynamic. Do not put cues in notes[].
  List excluded cue passages in meta.repeats free text (e.g. "Cue notes excluded: Trbni I,II. bars 15–17").
- Flauto II doubling: "muta in Fl. picc." / "muta in Fl. II." instructions change the instrument — record the bar in
  meta.repeats text (e.g. "muta in Fl. picc. at bar N"); the notes themselves stay pitch-encoded as written.
- Rehearsal letters (A, B, C ... printed above the staff) -> meta.rehearsal [{"mark":"A","bar":N}].
- Flute is not transposing: written pitch IS concert pitch. Scientific octaves, C4 = middle C.
- flag every doubtful note with "uncertain":"unc" (pitch, octave, accidental, duration, bar alignment).

## Output: write BOTH files at the FINAL paths (not work/):
- project/dvorak/symphony-no-8/flute-<i|ii>/dynamic/pages/notes_pPP.json   (PP = 2-digit PDF page: 01..26)
- project/dvorak/symphony-no-8/flute-<i|ii>/dynamic/pages/bars_pPP.json

notes_pPP.json schema (copy the committed model project/dvorak/symphony-no-8/trombone-i/dynamic/pages/notes_p01.json):
{"page":PP,
 "movements":[{"mvt":"I|II|III|IV","starts_at":{"sys":S,"x":X}}],      // movement headings on this page, [] if none
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#5","clef":"G","bar":25,
           "dur":"1/4","off":"1/2","tie_from_prev":false,"uncertain":""}, ...],
 "meta":{"bars":[first,last] or {"I":[a,b],"IV":[c,d]} when multiple movements share the page,
         "meters":[{"bar":1,"meter":"4/4","mvt":"I"}],                  // include meter in force at top of page
         "tempos":[{"bar":1,"text":"Allegro con brio","mm":"♩=138","mvt":"I"}],
         "key_signatures":[{"bar":1,"key":"1 sharp","mvt":"I"}],
         "rehearsal":[{"mark":"A","bar":28}],
         "repeats":"free text: repeat barlines, 1st/2nd endings, D.S./Coda, fermatas, cues excluded, muta",
         "movement_last_bar":{"I":318}}}
- One entry per played notehead in reading order (top system -> bottom, left -> right); x,y = notehead centre in
  PAGE pixels (±10 px). Chords = one entry per notehead (same off).
- dur/off as fractions of a whole note ("1","1/2","3/4","1/4","1/8","1/16","1/12" triplet-eighth,"0" grace);
  off = onset from bar start. Every played note's dur+off must fit its bar's meter (check_rhythm.py must pass).
- bar = printed bar number (count carefully through multi-bar rests; verify against printed numbers every 5 bars).
- For simile/measure-repeat signs (𝄎), re-emit the repeated notes with "sim":true on each emitted note.

## Then: bar segments for every bar
work/bars_auto_pPAGE.json (make it with `python3 tools/dynamic/bars_auto.py PAGE`) lists auto-detected barline
segments per system ({"xa","xb","multi","label":""}) — UNRELIABLE here:
it misses multi-bar-rest boundaries and flags stems as barlines. Write bars_pPP.json with the same structure
({"1":[{"xa":X,"xb":X,"label":"N" or "N–M"}, ...], "2":[...]...} keyed by system number string), fixing
false/missed barlines and giving every segment its printed bar number; multi-bar rests as ranges "61–64" (en dash).
Every note you listed must fall inside the segment carrying its bar number. Verify with
`python3 tools/dynamic/bars_overlay.py PAGE project/.../bars_pPP.json` (work/barsov_pPAGE_*.png).

Reply briefly (structured output): page, part dir, note count, bars range per movement, movements/meters/tempos/key
signatures seen, rehearsal letters, repeats/muta text, cue passages excluded, uncertain count, issues list.
Do not edit any other files. Do not commit work/ artefacts — only the two JSONs under project/.
