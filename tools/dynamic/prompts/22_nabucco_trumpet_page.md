# Task: transcribe ONE page of the trumpet II part (Verdi, Nabucco) — pitch AND rhythm AND bar segments

Working dir: the repository root, on branch `devin/decode-nabucco-trumpet2`
(`git fetch origin devin/decode-nabucco-trumpet2 && git checkout devin/decode-nabucco-trumpet2` if not already on it).
Your page image arrives as an attachment: save it as `work/pPAGE.png` (300 dpi grayscale, ~2973x3912 px).
PAGE = the PDF page number of the whole 32-page "TROMBA II" part (the Sinfonia plus the opera numbers).

Tools (python3 = ~/venvs/dynamic/bin/python):
- `python3 tools/dynamic/cand.py PAGE` -> work/cand_pPAGE.json note-head candidates + work/ov_pPAGE.png overlay.
- `python3 tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png (left/right halves of system SYS, 1-based from top).
  `python3 tools/dynamic/zoom.py PAGE SYS X0 X1 OUT.png` -> custom x range (~500–800 px close-ups).
  Pitch guides on the left: treble names (red/green), (bass) in grey. Blue x-ruler in page pixels at the top.
  Candidate circles are weak hints only (this engraving detects few real heads and some junk); find every head yourself.
- `python3 tools/dynamic/check.py PAGE` draws your work/final_pPAGE.json notes on the page (work/chk_pPAGE_*.png).
- `python3 tools/dynamic/check_rhythm.py PAGE` checks dur/off in work/final_pPAGE.json against the meters you wrote.
- `python3 tools/dynamic/bars_auto.py PAGE` -> work/bars_auto_pPAGE.json auto barline segments (weak hints).
- `python3 tools/dynamic/bars_overlay.py PAGE [work/bars_pPAGE.json]` -> work/barsov_pPAGE_*.png segment check images.

## Reading rules (important)
- Clef: **treble ("G")** for all played notes.
- **Crook ("in X")**: printed where it applies ("in Re" = D trumpet, "in Mi" = E, "in Mib" = Eb, "in Do" = C ...).
  A new number or tempo section may restate it ("in Re" under "Allegro marziale"). Record every crook instruction in
  meta.transpositions with its page-local bar. The pitch you write is the WRITTEN pitch as printed — do not transpose.
- **Key signature**: trumpet parts of this edition usually have NONE after the clef (accidentals are written inline,
  like horn parts). Check the clef area at the start of every system anyway; if a key signature appears, record it in
  meta.key_signatures and apply it. Apply accidentals within the bar and across ties into the next bar; a natural
  cancels. Be extremely careful with every ♭/♯/♮.
- **Number headings**: each opera number has a printed heading ("SINFONIA", "ATTO I. CORO D'INTRODUZIONE",
  "CAVATINA", "RECITATIVO e TERZETTINO", "Coro", "Finale I.", "ATTO II. SCENA ED ARIA", "RECITATIVO-PREGHIERA",
  "CORO DI LEVITI", "FINALE SECONDO", "ATTO III. CORO D'INTRODUZIONE", "RECITATIVO-DUETTO", "Coro di schiavi Ebrei",
  "ATTO IV. PRELUDIO, SCENA ED ARIA", "MARCIA FUNEBRE", ...). Bar counting RESTARTS at 1 at each heading. Record every
  heading on your page in "movements" with its {sys, x} position, and list the page regions in meta.regions.
- **Bar numbers**: no regular printed bar numbers. Anchors available: (a) multi-bar rest counters above the staff
  ("15" over a rest block = 15 consecutive rest bars — count them into the bar sequence), (b) BOXED numerals above the
  staff at tempo changes/entries — these are the absolute bar number inside the current number; verify your count
  agrees and report each in meta.anchors, (c) rehearsal letters A, B, C ... -> meta.rehearsal.
- **Measure-repeat signs** (𝄎 / a slash with two dots): for every such bar output the notes of the repeated bar again
  with "sim": true, same pitch/dur/off, y = staff middle line, x spread evenly inside the bar.
- **Cue notes EXCLUDED**: small noteheads labelled with another instrument or source — "(Tr.ba I.)", "(Archi)",
  "(Cor. IV. in Re)", "Viol.", "Ob." ... — often over a full-bar rest or with vocal cue text. List excluded cue
  passages in meta.repeats. When in doubt, keep the note but set "uncertain":"could be cue".
- Scientific octaves, C4 = middle C (treble bottom line = E4). dur/off as fractions of a whole note
  ("1/12" = triplet eighth, "0" = grace). off = onset from bar start. Every played note's dur+off must fit its meter.
- Flag every doubtful note "uncertain":"unc" or a short reason. Never guess silently.

## Output: write work/final_pPAGE.json and work/bars_pPAGE.json
final_pPAGE.json schema (bar numbering is PAGE-LOCAL: first bar on your page = 1):
{"page":PAGE,
 "movements":[{"mvt":"<verbatim printed heading>","starts_at":{"sys":S,"x":X}}],   // [] if none
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#4","clef":"G","bar":25,
           "dur":"1/4","off":"1/2","tie_from_prev":false,"sim":false,"uncertain":""}, ...],
 "meta":{"local_bar_count":N,
         "regions":[{"label":"<heading or 'cont.' for continuation of a number started earlier>",
                     "local_bars":[a,b]}],
         "anchors":[{"printed":20,"local":17,"sys":2,"x":1234}],
         "meters":[{"bar":1,"meter":"4/4"}],                 // include the meter in force at the top of the page
         "tempos":[{"bar":1,"text":"Allegro","mm":""}],
         "transpositions":[{"bar":1,"text":"in Re"}],
         "key_signatures":[{"bar":1,"key":"none"}],
         "rehearsal":[{"mark":"A","bar":70}],
         "repeats":"free text: repeat barlines, endings, D.S./Coda, fermatas, cues excluded, measure-repeat % bars",
         "movement_last_bar":{"<heading>":N}}}                // only if a number ENDS on your page (final double bar)
- One entry per played notehead in reading order; x,y = notehead centre in PAGE pixels (±10 px); chords = one entry
  per notehead (same off). If a bar is split across the page edge or a tie crosses the page end, say so in meta.repeats.

## Then bar segments for every bar
Make work/bars_auto_pPAGE.json with `python3 tools/dynamic/bars_auto.py PAGE`; inspect with
`python3 tools/dynamic/bars_overlay.py PAGE` (work/barsov_pPAGE_*.png). Write work/bars_pPAGE.json — same structure,
{"1":[{"xa":X,"xb":X,"label":"N" or "N–M"}...]} keyed by system number string — fixing false/missed barlines (stems
are often detected as barlines) and giving every segment its PAGE-LOCAL bar number; multi-bar rests as ranges
"61–64" (en dash). Where a number heading resets counting, the next segment is "1". Every listed note must fall
inside the segment carrying its bar number. Verify with `python3 tools/dynamic/bars_overlay.py PAGE work/bars_pPAGE.json`.

## Finish
Re-run `python3 tools/dynamic/check.py PAGE` and `python3 tools/dynamic/check_rhythm.py PAGE` (overfull bars and
overlaps are errors; short bars are fine — rests are invisible to it). Then upload the two files:
`upload_attachment` on work/final_pPAGE.json and work/bars_pPAGE.json, and report both URLs in structured output.
Do not commit anything; do not edit any other files.
