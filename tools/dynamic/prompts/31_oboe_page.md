# Task: transcribe ONE page of an oboe family part (Dvořák Symphony No. 8, Oboe I / Oboe II (C.ingl.)) — pitch AND rhythm AND bar numbers

Working dir: the repository root. Your page image: work/pPAGE.png (300 dpi grayscale, ~2968x3905 px).
PAGE = the PDF page number in the source PDF (the part's printed page number differs; the PDF page is what all tools use).

Tools (run them with `~/venvs/dynamic/bin/python` from the repo root; system python3 lacks cv2):
- `~/venvs/dynamic/bin/python tools/dynamic/cand.py PAGE` -> work/cand_pPAGE.json + work/ov_pPAGE.png (notehead candidates).
- `~/venvs/dynamic/bin/python tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png (left/right halves of system SYS, 1-based from top).
  `~/venvs/dynamic/bin/python tools/dynamic/zoom.py PAGE SYS X0 X1 work/OUT.png` -> custom x range (use ~500–800 px wide close-ups).
  Pitch guides on the left: treble names (red/green), (bass) in grey, [alto] in purple — each tick is exactly at that
  line/space height. A blue x-ruler in PAGE pixel coordinates is at the top. Candidate noteheads are
  circled — they are only weak hints (many real notes are missed and some candidates are junk like dynamics or rests); find every notehead yourself.
- `~/venvs/dynamic/bin/python tools/dynamic/check.py PAGE` draws your notes on the page (work/chk_pPAGE_*.png) — run it after writing the JSON and LOOK at every image to fix misplaced/missing/extra notes.
- `~/venvs/dynamic/bin/python tools/dynamic/check_rhythm.py PAGE` checks durations/offsets against the meter.
- `~/venvs/dynamic/bin/python tools/dynamic/make_bars_auto.py PAGE` drafts work/bars_auto_pPAGE.json (needs final_pPAGE.json first).
- `~/venvs/dynamic/bin/python tools/dynamic/bars_overlay.py PAGE` -> work/barsov_pPAGE_*.png segment overlay.

## Reading rules (important)
- The part is in **treble clef** throughout (oboe and cor anglais read treble). Report `clef`:"G" for every note.
- **Key signature**: read it at the start of every system — it changes between movements (and once mid-movement-IV). Apply it
  to every note at that letter in all octaves unless cancelled (for the rest of that bar). Also apply accidentals that persist
  within the bar and carry over ties. Double-check every F/F#, C/C#, B/Bb — dropped flats/sharps were a past complaint.
- EXCLUDE cue notes (small noteheads, usually labelled with another instrument e.g. "Fl.I.", "Viol.I.", "Ob.II.", "Timp.",
  "Cor", "Cl.", "Fg.", often with a rest in the same bar). Compare notehead size with clearly normal notes.
- Oboe/cor anglais pitches: write the WRITTEN pitch (as printed) in scientific notation (C4 = middle C).
- Grace notes: pitch + "dur":"0", "off" at their position.
- Measure-repeat signs (％): write that bar's notes with "sim": true.
- Stacked/chord notes do not occur in this part; if you think you see one it is two nearby melodic notes — look again.

## Output 1: work/final_pPAGE.json  (WRITE THIS EARLY, as soon as pitches are read — before rhythm)
{"page":PAGE,
 "movements":[{"mvt":"I|II|III|IV","starts_at":{"sys":S,"x":X}}],      // only movement headings actually printed on this page
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#5","clef":"G","bar":25,
           "dur":"1/4","off":"1/2","tie_from_prev":false,"uncertain":""}, ...],
 "meta":{"bars":[first,last] or {"I":[a,b],"II":[c,d]},                // actual printed bar range on this page, incl. rest bars
         "meters":[{"bar":1,"meter":"3/4","mvt":"I"}],                 // every time signature; also the meter in force at page top even if not reprinted (C = 4/4, ¢ = 2/2)
         "tempos":[{"bar":1,"text":"Allegro con brio","mm":"♩=138","mvt":"I"}],
         "key_signatures":[{"bar":1,"key":"1 sharp","mvt":"I"}],
         "transpositions":[{"bar":233,"text":"Ob.II. muta in C.ingl.","mvt":"I"}],   // any muta/instrument-change instruction
         "repeats":"free text: repeat barlines, 1st/2nd endings (which bars), D.S./Coda/segno, measure-repeat signs, fermatas",
         "movement_last_bar":{"I":318}}}
- One entry per played notehead in reading order (system by system, left to right); x,y = notehead centre in PAGE pixels (±10 px).
- "bar" must be filled for EVERY note: the printed bar number. Printed numbers appear about every 5 bars — count carefully
  through multi-bar rests and verify against them.
- "dur" = written duration as a fraction of a whole note ("1","1/2","3/4","1/4","3/8","1/8","3/16","1/16","1/32";
  triplet eighth = "1/12", triplet quarter = "1/6", grace = "0").
- "off" = onset from the start of its bar, fraction of a whole note (first beat = "0"). Work it out from the rests/notes before it.
- "tie_from_prev": true if this notehead is the tied continuation of the previous note.
- "uncertain": "" or a short note (e.g. "could be cue", "pitch A5 or G5").
- Tied notes each keep their own dur/off.

## Output 2: work/bars_pPAGE.json
First run `make_bars_auto.py PAGE` to draft work/bars_auto_pPAGE.json, then view it with bars_overlay.py.
Write work/bars_pPAGE.json with the same structure — per system (key = system number 1-based from top) a list of
{"xa": left barline x, "xb": right barline x, "label": printed bar number as a string}:
- Fix false barlines (stems detected as barlines: merge the two segments) and missed ones (split a segment).
- Every segment gets its printed bar number; multi-bar rests get a range "61–64" (en dash). The first segment of each
  system starts at the system start; drop any tiny trailing segment after the final barline.
- Movement restarts numbering at 1. Every note in final_pPAGE.json must fall inside the segment carrying its bar number.
- Verify with `~/venvs/dynamic/bin/python tools/dynamic/bars_overlay.py PAGE work/bars_pPAGE.json` and LOOK at the images.

## English horn doubling (Oboe II pages only)
Where the part prints "[Ob.II. muta in C.ingl.]", the player switches to cor anglais: every printed note after it — until
"[muta in Ob.II.]" — is played on English horn. Transcribe those notes normally (written pitch as printed) but add
"instr":"english-horn" to each such note, record both muta markings in meta.transpositions, and report the exact bar range.

## Quality bar
Go through EVERY system of the page (zoom both halves). After writing, run check.py and look at all overlay images;
run check_rhythm.py and fix real errors (overfull bars, overlapping notes). Reply with: note count, movements, meters/tempos/
key signatures found, repeats, the C.ingl. bar range if any, and the list of uncertain items.
