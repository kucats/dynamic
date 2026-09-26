# Task: transcribe ONE page of a cello part (Dvořák Symphony No. 8, Violoncello) — pitch + rhythm + bar numbers

Working dir: <repo-working-dir>. Your page: work/pPAGE.png (300 dpi grayscale, ~2967x3904 px).
The instrument is Violoncello — **non-transposing**: the written pitch IS concert pitch (C4 = middle C).

Tools prepared for you (run with `~/venvs/dynamic/bin/python` or `python3` if the venv has cv2 installed):
- `python3 tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png: left/right halves of system SYS
  (1-based from top). `python3 tools/dynamic/zoom.py PAGE SYS X0 X1 OUT.png` for a custom x range (~500-800 px
  for close-ups). Each image has a blue x-ruler in PAGE pixel coordinates, pitch guides at the left,
  and auto-detected notehead candidates circled (red = filled, magenta = hollow) with ids.
  Pitch guides: treble names in red/green, (bass) names in grey brackets, [alto] names in purple brackets —
  each tick sits exactly on that line/space height.
- work/cand_pPAGE.json: the candidates (sys, x, y, kind, treble pitch guess, cid). HINTS ONLY — many real
  notes are missing (hollow heads, ledger lines, beamed groups, tenor-clef notes) and some candidates are
  junk (dynamics, numbers, rests, clefs). Never trust the guessed pitch; read every notehead yourself.
- `python3 tools/dynamic/mk_bars_auto.py PAGE` -> work/bars_auto_pPAGE.json: detected barline segments plus
  labels guessed from the bar numbers you already assigned to notes. Segments use the same system
  numbering as cand_pPAGE.json.
- `python3 tools/dynamic/bars_overlay.py PAGE [work/bars_pPAGE.json]` -> work/barsov_pPAGE_*.png.
- `python3 tools/dynamic/check.py PAGE` -> work/chk_pPAGE_*.png: your notes drawn on the page with pitch labels.
- `python3 tools/dynamic/check_rhythm.py PAGE`: reports bars whose dur/off disagree with the meter.

## Clefs (cello specifics — IMPORTANT)
- The part is mostly **bass clef** (F clef on the 4th line; bottom line = G2). Use the grey (bass) guides.
- **Tenor clef** (C clef centred on the 4th line = C4) appears in high passages: lines bottom-up are
  D3 F3 A3 C4 E4. The purple [alto] guides assume C4 on the MIDDLE line — for tenor clef subtract a third
  from the alto label (alto E4 = tenor C4, alto C4 = tenor A3) or read the staff directly.
- **Treble clef** for the highest passages: use the red/green guides.
- Clefs can change mid-system — watch for a clef printed before a barline or between phrases.
- Report clef per note as "bass" | "tenor" | "treble".

## Pass 1 — pitch -> work/final_pPAGE.json
{"page":PAGE,
 "movements":[{"mvt":"I|II|III|IV","starts_at":{"sys":S,"x":X}}...],   // only movement headings ON this page
 "notes":[ {"sys":1,"x":1234,"y":567,"pitch":"Bb2","clef":"bass","bar":25,"tie_from_prev":false,
            "sim":false,"uncertain":""}, ...]}

- One entry per notehead the cellist actually plays, in reading order (system by system, left to right).
  Chords/double-stops: include every notehead of the stack.
- pitch: the WRITTEN pitch as printed, scientific notation (C4 = middle C, bass bottom line = G2,
  tenor bottom line = D3, treble bottom line = E4), letter + 'b'/'#' + octave, e.g. "F#3", "Eb3", "A2".
  Apply the KEY SIGNATURE plus printed accidentals; an accidental lasts until the end of the bar for the
  same staff position and carries over a tie into the next bar; a natural cancels it. Be extremely careful
  with flats/sharps (dropped accidentals were specifically complained about before).
- Key signature: read it at the start of EVERY system (it can change at movement headings or mid-page).
  Movement I is in G major (1 sharp) — verify on the page rather than assuming.
- x,y: notehead centre in PAGE pixel coordinates (x from the ruler, y from the candidate or pitch guide;
  ±10 px is fine).
- bar: printed bar number (small numbers printed every 5 bars — usually below the staff — plus multi-bar
  rest counts), else null.
- tie_from_prev: true if this notehead is the tied continuation of the previous note of the same pitch.
- sim: true for CUE notes — small noteheads of other instruments, labelled e.g. "Vl.I", "Vlc.II", "Cb.",
  "Fl.", "Ob.", "Fg.", "Tr.", "Timp.", often with a whole-bar rest in the same bar. Compare notehead size
  with clearly normal notes; when unsure whether a note is a cue, include it with sim:true AND mark uncertain.
- uncertain: "" or a short note ("pitch A3 or G3", "maybe cue", "could be D4").
- movements: record each movement heading (I/II/III/IV) that starts on this page with its system and x.
Then run check.py and fix misplaced/missing/extra notes and wrong pitches.

## Pass 2 — rhythm + timing (update work/final_pPAGE.json IN PLACE)
Keep every existing field. Add per note:
- "dur": written duration as a fraction string of a WHOLE note: "1" whole, "1/2" half, "3/4" dotted half,
  "1/4", "3/8" dotted quarter, "1/8", "3/16", "1/16", "1/32"; triplet eighth = "1/12", triplet quarter =
  "1/6", triplet sixteenth = "1/24"; grace note = "0".
- "off": onset from the start of its bar as a fraction of a whole note (beat 1 = "0"; in 2/4 the second
  eighth = "1/8"; in 4/4 beat 3 = "1/2"). Compute from the rests and note values before it in the bar.
  off+dur of the last note must never exceed the bar length. Tied notes keep their own dur/off.
- "bar": now REQUIRED for every note.
Add page-level "meta":
{"bars":[first_bar,last_bar],                       // rest bars included; {"I":[a,b],"II":[c,d]} if two
                                                    // movements share the page
 "meters":[{"bar":N,"meter":"4/4","mvt":"I"},...],  // every time signature in force (C = 4/4, ¢ = 2/2);
                                                    // include the one in force at the page's first bar
 "tempos":[{"bar":N,"text":"Allegro con brio","mm":"♩=138","mvt":"I"},...],   // tempo words + metronome
                                                                            // marks, mm "" if none
 "key_signatures":[{"bar":N,"key":"1 sharp"/"3 flats"/"none","mvt":"I"},...], // every printed signature
 "rehearsal":{"A":26,...},                          // rehearsal letters -> bar numbers
 "repeats":"free text: repeat barlines, 1st/2nd endings (which bars), segno, 'Dal Segno e poi la Coda',
            CODA starts, fermatas on rests, measure-repeat signs; or ''",
 "movement_last_bar":{"II":170},                    // only if a movement ends on this page
 "clef_changes":"free text: where the clef changes (sys/bar)", "cues_excluded":"free text"}
Then re-run check.py and also check_rhythm.py; fix overfull bars and overlapping notes it reports
(short bars are fine — it cannot see rests).

## Pass 3 — bar numbers -> work/bars_pPAGE.json
work/bars_auto_pPAGE.json holds {"SYS":[{"xa":left,"xb":right,"label":"N or ''"},...]} between detected
barlines. Run bars_overlay.py PAGE first to see segments on the page.
Write work/bars_pPAGE.json with the same structure but CORRECT and COMPLETE labels:
- every segment gets its printed bar number as a string, e.g. "57";
- a multi-bar rest segment gets a range "61–64" (en dash);
- drop false barlines (stems detected as barlines — common in dense beamed passages), split segments where
  a real barline was missed, remove the tiny tail segment after a system's final barline; the first segment
  starts at the system start;
- a movement heading restarts numbering at 1 — labels after it count from 1 again;
- keep xa/xb in PAGE pixels.
Then bars_overlay.py PAGE work/bars_pPAGE.json and verify every label against the printed numbers every
5 bars and multi-rest counts.

## Report
Notes count, bar range covered, movements on the page, clef changes, key signatures, and any uncertain items.
