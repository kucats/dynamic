# Task: transcribe written pitches of ONE page of a horn part (Dvořák Symphony No. 8, Corno II)

Working dir: <repo-working-dir>. Your page: work/pPAGE.png (300 dpi grayscale scan, ~2968x3904 px).
Tools already built for you:
- `python3 work/zoom.py PAGE SYS` -> writes work/z_pPAGE_sSYS_a.png and _b.png (left/right halves of system SYS, 1-based from top).
  `python3 work/zoom.py PAGE SYS X0 X1 OUT.png` -> custom x range (use for close-ups, e.g. 400 px wide).
  Each image has: a blue x-ruler in PAGE pixel coordinates at the top, pitch guides at the left
  (treble names in red/green, bass-clef names in grey brackets; each guide tick is exactly at that line/space height),
  and auto-detected notehead candidates circled with an id (red = filled, magenta = hollow guess).
- work/cand_pPAGE.json: the candidates (sys, x, y, kind, treble-pitch guess, cid). They are ONLY hints: many real notes
  (especially half/whole notes, notes on ledger lines, notes touching beams) are missing, and some candidates are junk
  (dynamics letters like p/d, numbers, rests, cue notes). Do not trust the guessed pitch; read it yourself.
View images with the Read tool. Zoom in (custom range ~500-800 px wide) whenever anything is unclear.

## What to produce
Write work/final_pPAGE.json:
{"page":PAGE,
 "movements":[{"mvt":"I|II|III|IV","starts_at":{"sys":S,"x":X}}...],   // only movement starts that are ON this page
 "notes":[ {"sys":1,"x":1234,"y":567,"pitch":"Bb4","clef":"G","bar":25,"tie_from_prev":false,"uncertain":""}, ...]}
- One entry per notehead that the Horn II player actually plays, in reading order (system by system, left to right).
- EXCLUDE cue notes (small noteheads of other instruments, usually labelled e.g. "Viol.I", "Trbe", "Ob.", "Vlc.,Cb.", "Timp.",
  "Cor.I", often with a full-bar rest printed in the same bar). Compare notehead size with clearly normal notes.
  Exclude rests, and notes of a *different* horn that are explicitly cued. If two notes are stacked (both played), include both.
- x,y = centre of the notehead in PAGE pixel coordinates (read x from the ruler; y can come from the candidate or the guide;
  accuracy ±10 px is fine).
- pitch = the WRITTEN pitch as printed, in scientific notation (C4 = middle C; treble clef bottom line = E4, bass clef bottom
  line = G2), letter + optional 'b' or '#' (or 'n' is not needed) + octave, e.g. "F#4", "Eb5", "C3".
  Apply accidentals exactly as a musician would: an accidental lasts until the end of the bar for the same staff position,
  carries over a tie into the next bar, and is cancelled by a natural. There is normally no key signature in horn parts,
  but check the clef area of each system and apply one if present. Be extremely careful with flats/sharps/naturals
  (the user specifically complained about dropped flats before).
- clef: "G" for treble, "F" for bass clef (report the pitch as it reads in bass clef, e.g. "C3"). Clefs can change mid-system.
- bar: printed bar number if you can determine it (count from the printed numbers above the staff and multi-bar rests), else null.
- tie_from_prev: true if this note is the tied continuation of the previous note (same pitch joined by a tie).
- uncertain: empty string, or a short note if you are not sure (e.g. "could be cue", "pitch A4 or G4").
- movements: this part contains movements I–IV across pages 9–15. Record where a movement heading (I, II, III, IV) starts on
  your page, if any.

## Quality bar
Go through every system of the page. After writing the JSON, run
`python3 work/check.py PAGE` which draws your notes on the page (work/chk_pPAGE_*.png) with their labels; look at all of them
and fix any misplaced/missing/extra notes or wrong pitches. Then reply with: number of notes, movements found, and a list of
any uncertain items. Do not edit any other files.
