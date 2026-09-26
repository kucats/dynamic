# Task: transcribe ONE page of a violin part (Dvořák Symphony No. 8, Violin I) — pitch AND rhythm

Working dir: the repository root on branch `devin/decode-violin1`. Your page image: `work/pPAGE.png`
(300 dpi grayscale, ~2964x3900 px; PDF pages 1–13 of `work/violin1.pdf`, all are Violino I).

Setup (do once):
- `git fetch origin devin/decode-violin1 && git checkout devin/decode-violin1`
- `mkdir -p work`
- `curl -sL "https://drive.usercontent.google.com/download?id=1QZpD2sOQBJdLFwu2ZbamzsYNIY5G9JSf&export=download&confirm=t" -o work/violin1.pdf`
- Python: use `~/venvs/dynamic/bin/python` for every command below (it has cv2 + pymupdf). If that venv is
  missing: `python3 -m venv ~/venvs/dynamic && ~/venvs/dynamic/bin/pip install opencv-python-headless numpy pillow pymupdf`
- Render your page (PAGE = your page number):
  `~/venvs/dynamic/bin/python -c "import fitz;d=fitz.open('work/violin1.pdf');pg=d[PAGE-1];pg.get_pixmap(dpi=300,colorspace=fitz.csGRAY).save('work/pPAGE.png')"`
- Copy the reviewed staff layout for your page so the tools use it:
  `~/venvs/dynamic/bin/python -c "import json;d=json.load(open('project/dvorak/symphony-no-8/violin-i/dynamic/systems.json'))['pages'];json.dump({'systems':d['PAGE']},open('work/systems_pPAGE.json','w'))"`
  (PAGE here is a decimal string, e.g. d['4'] for page 4)
- `~/venvs/dynamic/bin/python tools/dynamic/cand.py PAGE`  (produces work/cand_pPAGE.json)

Tools (use `~/venvs/dynamic/bin/python` — it has cv2):
- `~/venvs/dynamic/bin/python tools/dynamic/zoom.py PAGE SYS` -> `work/z_pPAGE_sSYS_a.png` / `_b.png` (left/right halves of
  system SYS, 1-based from top, where SYS indexes the reviewed system list in systems_pPAGE.json).
  `~/venvs/dynamic/bin/python tools/dynamic/zoom.py PAGE SYS X0 X1 OUT.png` -> custom x range (use ~500–800 px wide close-ups).
  Pitch guides on the left: treble names (red/green), (bass) in grey, [alto] in purple — each tick is exactly
  at that line/space height. A blue x-ruler in PAGE pixel coordinates is at the top. Candidate noteheads from
  `work/cand_pPAGE.json` are circled — they are only weak hints (this engraving is poorly detected); find
  every notehead yourself. Read the system at BOTH half-zoom levels before trusting a note.
- `~/venvs/dynamic/bin/python tools/dynamic/check.py PAGE` draws your notes on the page (work/chk_pPAGE_*.png).
- `~/venvs/dynamic/bin/python tools/dynamic/check_rhythm.py PAGE` checks durations/offsets against the meter.
Both read `work/final_pPAGE.json`, so iterate there first — `work/final_pPAGE.json` is your draft file with
the exact `notes_pNN.json` structure below; only copy it to `project/.../pages/notes_pNN.json` when clean.
- `~/venvs/dynamic/bin/python tools/dynamic/bars_overlay.py PAGE [bars.json]` renders bar segments for verification.

## Reading rules (important)
- The part is in **treble clef** throughout. BUT cue lines appear in other clefs (bass clef for
  "Vlc."/"Cb." cues, alto/tenor C-clef for "Vle." cues) — record their `clef` honestly.
- **Key signature**: read it at the start of EVERY system — it changes several times inside this part
  (movement I: 1 sharp; II: 3 flats; III: 2 flats, then changes mid-movement; IV: 1 sharp with a long
  flat-key middle section). Apply it to every matching pitch name in all octaves unless a natural cancels it
  (for the rest of that bar). Also apply accidentals within the bar and across ties. Double-check every
  B/Bb, E/Eb, F/F#, C/C# — the user specifically complained about dropped flats/sharps before.
- **Cue notes**: INCLUDE them but mark `"sim": true` (small noteheads, usually labelled with another
  instrument name such as "Vlc.", "Cb.", "Vle.", "Fl." — often beside a rest in the same bar). If a note
  might be a cue but you cannot tell (no label, normal size), include it with `uncertain` text instead.
- Violin is not transposing: the written pitch IS concert pitch. Scientific octaves (C4 = middle C);
  treble bottom line = E4, top line = F5; ledger lines above go G5, A5, B5, C6, D6, E6...
- For stacked double stops (two noteheads sharing a stem, both played by the same player), include BOTH
  notes at the same `x`. Divisi or chords are played; do not skip them.

## Output files (both required)

### `project/dvorak/symphony-no-8/violin-i/dynamic/pages/notes_pNN.json`  (NN = zero-padded page, e.g. p04)
```json
{"page":PAGE,
 "systems":[[...5 floats per system, copied verbatim from systems_pPAGE.json...]],
 "movements":[{"mvt":"I|II|III|IV","starts_at":{"sys":S,"x":X}}],
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#4","clef":"treble|bass|alto|tenor","bar":25,
           "dur":"1/4","off":"1/2","tie_from_prev":false,"uncertain":"","sim":false}, ...],
 "meta":{"bars":[first,last] or {"I":[a,b],"IV":[c,d]},
         "meters":[{"bar":1,"meter":"3/4","mvt":"I"}], "tempos":[{"bar":1,"text":"Allegro con brio","mm":"138","mvt":"I"}],
         "key_signatures":[{"bar":1,"key":"1 sharp","mvt":"I"}],
         "repeats":"free text: repeat barlines, 1st/2nd endings, D.S./Coda, fermatas", "movement_last_bar":{"I":318}}}
```
- One entry per played notehead in reading order (left→right per system, systems top→bottom);
  x,y = notehead centre in PAGE pixels (±10 px).
- dur/off as fractions of a whole note (triplet eighth = "1/12", grace = "0"); off = onset from the start
  of the bar. `check_rhythm.py` must report no unexplained overflow/underflow.
- `movements` lists a movement only when its heading (e.g. "II. Adagio", "IV. Allegro ma non troppo",
  "CODA Molto vivace") is printed on this page.
- bar = printed bar number (count carefully through multi-bar rests — a rest with a bold number above it
  covers that many bars; verify against the small printed numbers every 5 bars).
- `meta.repeats`: describe ALL repeat barlines, first/second endings ("1."/"2." brackets), and
  "Dal S."/"Coda" instructions with the bars they sit on — this part has a D.S. + Coda in movement III
  and first/second endings in movement IV. Treat first and second endings as SEPARATE bar numbers
  (linear numbering counts them as different bars).

### `project/dvorak/symphony-no-8/violin-i/dynamic/pages/bars_pNN.json`
`{"1": [{"xa":…,"xb":…,"label":"…"}], "2": [...], ...}` — one key per system (1-based), every bar segment
spanned by its left/right barlines with the printed bar number; multi-bar rests as ranges "61–64"
(en dash). Generate a draft with `~/venvs/dynamic/bin/python tools/dynamic/bars_auto.py PAGE`
(-> `work/bars_auto_pPAGE.json`), then FIX it by eye with
`~/venvs/dynamic/bin/python tools/dynamic/bars_overlay.py PAGE` — auto-detection confuses stems for barlines and misses the
thin end-of-system line. Label EVERY segment (single bar number or multi-bar range); a segment that is a
1st/2nd ending gets its own number as printed. Every note you listed must fall inside the segment carrying
its bar number.

## Commit
`git checkout -b devin/decode-violin1-pNN` BEFORE writing outputs (NN = your zero-padded page).
Copy the clean `work/final_pPAGE.json` to `project/dvorak/symphony-no-8/violin-i/dynamic/pages/notes_pNN.json`
and your verified bars file to `project/dvorak/symphony-no-8/violin-i/dynamic/pages/bars_pNN.json`.
Commit ONLY the two pages/*.json files; never commit work/, the PDF, renders, or crops.
`git push -u origin devin/decode-violin1-pNN` when done.

Reply via structured output: page, note count, bar range, uncertain count, branch, status
("ok" | "partial" | "failed"), and any issues (ambiguous bars, missing cues, tool problems).
Do not edit any other files.
