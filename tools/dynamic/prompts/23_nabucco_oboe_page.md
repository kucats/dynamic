# Task: transcribe ONE page of the combined oboe part (Verdi, Nabucco — "OBOE I. - CORNO INGLESE") — pitch, rhythm, bars

Working dir: the repository root, on branch `devin/decode-nabucco-oboe`.
Your page image: work/pPAGE.png (300 dpi grayscale, ~2970x3900 px; PAGE = physical PDF page 1-42).
The whole PDF is ONE combined part for the player who doubles Oboe I and Corno Inglese (English Horn).
In the Sinfonia (PDF pages 1-4) the staff is Oboe I music; passages explicitly marked "Corno Inglese"/
"(C'ingl.)" belong to the english-horn decode (record their bars/notes and mark them in meta.regions).

Tools (python3 = ~/venvs/dynamic/bin/python, run from repo root):
- `python3 tools/dynamic/cand.py PAGE` -> work/cand_pPAGE.json candidates + work/ov_pPAGE.png overlay.
- `python3 tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png (left/right halves of system
  SYS, 1-based from top). `zoom.py PAGE SYS X0 X1 OUT.png` -> custom x range (~500-800 px close-ups; use them
  whenever a run, chord, or ledger-line area is ambiguous). Left margin pitch guides: treble names
  (red/green), (bass) grey, [alto] purple, <tenor> cyan/orange — every tick is exactly that line/space height.
  Blue x-ruler at top = PAGE pixel coordinates. Circled candidates are weak hints only — find every head yourself.
- `python3 tools/dynamic/check.py PAGE` draws your work/final_pPAGE.json notes back on the page
  (work/chk_pPAGE_*.png) — always inspect it.
- `python3 tools/dynamic/check_rhythm.py PAGE` checks dur/off against the meters you wrote.
- `python3 tools/dynamic/make_bars_auto.py PAGE` drafts work/bars_auto_pPAGE.json;
  `python3 tools/dynamic/bars_overlay.py PAGE [work/bars_pPAGE.json]` draws the segments for checking.

## Reading rules (important)
- Clef: **treble ("G")** throughout. Oboe I is non-transposing: written pitch = concert pitch
  (C4 = middle C; treble bottom line = E4).
- **Key signatures ARE printed** (Sinfonia opens with 3 sharps = A major). Read the clef area of EVERY
  system — the signature can change at movement/section headings or mid-page double bars. Record each in
  meta.key_signatures with the page-local bar where it takes effect, and apply it to every note of that
  letter in all octaves.
- Accidentals persist within a bar on the same staff position and carry over ties into the next bar;
  a natural cancels. Be extremely careful with every ♭/♯/♮ (dropped accidentals were a past complaint).
- **Divisi / two-oboe writing**: when two rhythmic voices share the staff (stems up vs down) the upper is
  Ob.I and the lower Ob.II — transcribe BOTH voices (each notehead its own entry; mark the lower voice with
  `"uncertain":"ob2"` is NOT needed — just include every played head; the split into parts happens later).
  "a2"/unison writing is one entry per notehead.
- **Cue notes** (small heads under a label like "Clar.", "Cor.", "Vl.", vocal cue text, or with a rest in
  the same bar): EXCLUDE them; list the passages in meta.cues_excluded. Unsure → keep with
  `"uncertain":"could be cue"`.
- **Measure-repeat signs** (% or slash+two dots, sometimes numbered): output the repeated bar's notes again
  with `"sim":true`, same pitch/dur/off, y = staff middle line, x spread evenly inside the bar.
- **Tremolo / repeated-note shorthand** (strokes through the stem): record the written note with its notated
  duration and `"uncertain":"tremolo"` — do not expand.
- **"Vuota" bars** are explicit empty bars — each counts as one bar; emit no notes.
- Grace notes are played: keep them with `"dur":"0"`.
- Dynamics/bowings/fingerings are not recorded; DO record rehearsal marks (boxed letters/numbers) into
  meta.rehearsal and tempo words / metronome marks into meta.tempos.

## Bar numbers — PAGE-LOCAL
No printed bar numbers. First bar region on the page = local 1; multi-bar rests count their full printed
length; % bars, Vuota bars, and 1st/2nd endings each count as one bar. Count continuously across any
mid-page movement/section boundary — meta.regions disambiguates. If the page begins inside a bar that
started on the previous page, that partial bar is local bar 0 (not counted in local_bar_count) and
meta.continues_from_prev=true; if it ends mid-bar, meta.continues_to_next=true.

## Movement headings
New centered headings ("SINFONIA", "ATTO I. CORO D'INTRODUZIONE", ...) go into "movements" with
{"mvt":"<verbatim>","starts_at":{"sys":S,"x":X}}. An inline "Andantino"/"Più mosso"/"Recit." over the staff
is a tempo mark inside the same movement, NOT a heading. A "(Tace)"/"Tacet" note means the instrument is
silent for the next number — record it in issues.

## Output — work/final_pPAGE.json then work/bars_pPAGE.json
{"page":PAGE,
 "movements":[{"mvt":"Sinfonia","key":"S","starts_at":{"sys":S,"x":X}}],
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#5","clef":"G","bar":3,"dur":"1/4","off":"1/2",
           "tie_from_prev":false,"sim":false,"uncertain":"","page_local_bar":3}, ...],
 "meta":{"bars":[1,N],
         "regions":[{"label":"<heading or 'cont.'>","local_bars":[a,b]}],
         "meters":[{"bar":1,"meter":"4/4"}],           // include the meter in force at the top of the page
         "tempos":[{"bar":1,"text":"Andante","mm":""}],
         "key_signatures":[{"bar":1,"key":"3 sharps"}],
         "rehearsal":[{"mark":"A","bar":70}],
         "repeats":"free text: repeat barlines, endings, segno/coda, fermatas, % chains, multi-rests",
         "local_bar_count":N,
         "continues_from_prev":false, "continues_to_next":false,
         "movement_last_bar":{},
         "clef_changes":"", "cues_excluded":""}}
- Write final_pPAGE.json as soon as pitches are read, then extend it in place with dur/off/meta.
- One entry per played notehead in reading order (system by system, left to right); x,y = notehead centre
  in PAGE pixels (±10 px). Rests produce no entries. dur/off = fractions of a whole note (triplet eighth
  "1/12", grace "0"); off = onset from bar start. off+dur must never exceed the bar length.
- Then make_bars_auto.py PAGE, bars_overlay.py PAGE, and write work/bars_pPAGE.json with CORRECT page-local
  labels: every segment its number, multi-rest segment a range "61–64" (en dash), merge false "barlines"
  (stems), split missed real ones, drop tiny tails. Labels strictly increase along and across systems; every
  note must fall inside the segment carrying its bar.
- Re-run check.py, check_rhythm.py, bars_overlay.py PAGE work/bars_pPAGE.json and re-inspect the images.

## Report
Note count, local bar range, headings, key signatures, meters/tempos, rehearsal marks, continues flags,
uncertain items. Never commit the PDF or any .png; do not edit files outside work/.
