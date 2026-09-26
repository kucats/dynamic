# Task: transcribe ONE page of a two-voice bassoon part (Verdi, Nabucco — Sinfonia, Fagotti staff) — pitch, rhythm, bars

Working dir: the repository root (the checked-out kucats/dynamic clone, typically ~/repos/dynamic). Your page image: work/pPAGE.png (355 dpi grayscale, ~3515x4620 px).
(PAGES 1–4 = the Sinfonia of the combined "FAGOTTO I." part: Fagotto I and II share ONE staff.)

Use ~/venvs/dynamic/bin/python for every script (system python3 lacks cv2).

Tools:
- `~/venvs/dynamic/bin/python tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png (left/right halves of system SYS, 1-based from top).
  `~/venvs/dynamic/bin/python tools/dynamic/zoom.py PAGE SYS X0 X1 OUT.png` -> custom x range (use ~500–800 px wide close-ups).
  Pitch guides on the left: treble names (red/green), (bass) in grey parens, [alto] in purple, **{tenor} in brown braces** — each tick is exactly at that line/space height. A blue x-ruler in PAGE pixel coordinates is at the top. Candidate noteheads from work/cand_pPAGE.json are circled — they are only weak hints (this engraving is poorly detected); find every notehead yourself.
- `~/venvs/dynamic/bin/python tools/dynamic/check.py PAGE` draws your notes on the page (work/chk_pPAGE_*.png).
- `~/venvs/dynamic/bin/python tools/dynamic/check_rhythm.py PAGE` checks durations/offsets against the meter (per voice).
- `~/venvs/dynamic/bin/python tools/dynamic/mk_bars_auto.py PAGE` builds work/bars_auto_pPAGE.json from your notes; `~/venvs/dynamic/bin/python tools/dynamic/bars_overlay.py PAGE` renders it for review.

**Write work/final_pPAGE.json as soon as the pitches are read** (before rhythm), then update it in place. Do not edit any other files, do not touch git, do not delete files.

## Voice assignment ("v" field) — ONE staff carries BOTH bassoons
- "v": 1 = Fagotto I (upper voice), 2 = Fagotto II (lower voice), 12 = both bassoons play the same printed notehead (unison / "a 2" / a single line clearly meant for both).
- A dyad (two heads sharing one stem): v1 gets the UPPER head, v2 the LOWER head — two entries at the same x.
- Independent voices with opposite stems: stems up = 1, stems down = 2.
- A single-note line: v=12 when the context is tutti/unison doubling (watch for "a 2", "a2", both voices resuming after it); v=1 when it is clearly a first-bassoon solo ("I.", "Solo", "1." markings, or printed rests/a part-count for the second voice). If truly ambiguous, take your best reading AND write a short "uncertain" note.
- When one voice has printed rests while the other plays, only the playing voice gets notes (the rest bars still get bar labels in bars_pPAGE.json).

## Reading rules (important)
- Clefs: **bass clef** is the norm; WATCH for a **tenor clef** (C clef centered on the 4th line from the bottom = second line from the top) in high passages — it can appear mid-system. When tenor clef is in force, read pitch from the {tenor} brown guide. Report "clef":"bass"|"tenor" on every note.
- **Key signatures change often** in this Sinfonia (e.g. 2 sharps ↔ 1 flat ↔ 3 sharps ↔ open). Read the key signature at the start of EVERY system and at every double barline, and apply it to every note of that letter in all octaves. Accidentals last until the end of the bar for the same staff position and carry over ties. The user specifically complained about dropped flats before — be careful with every ♭/♯/♮.
- This edition prints small **counting numbers** above some rest bars and solo passages (1 2 3 …) — counting aids, NOT bar numbers. Also multi-bar rests as thick bars with a big number, individually numbered single-bar rests ("3","4",…"9" — one bar each), and "VUOTA" (empty/tacet) bars — all count as bars.
- **Measure-repeat signs** (a slash with two dots, "repeat the previous bar"): output the notes of the repeated bar again with `"sim": true`, same pitch/dur/off/v, `y` = the staff's middle line, `x` spread evenly inside that bar in onset order.
- EXCLUDE cue notes (small noteheads labelled with another instrument, e.g. "Ob.", "Clar.", "Trbe", with a rest in the same bar for the bassoon voice).
- Bassoon is non-transposing: the written pitch IS concert pitch. Scientific octaves: C4 = middle C; bass clef top line = A3, bottom line = G2.
- Grace notes dur="0". Triplets: triplet eighth = "1/12", triplet quarter = "1/6".
- **Bar numbers**: no absolute bar numbers are printed. Use PAGE-LOCAL numbering: first bar on your page = 1, multi-bar rests count their full length, repeat-sign bars count as bars, VUOTA bars count. If a bar is split across the page end (tie into the next page) or a movement/section boundary is mid-page, say so in issues.
- tempos/meta: record every tempo word (Andante, Allegro, Andantino, Più mosso, rall., cresc.), meter changes, key-signature changes, rehearsal letters (A, B, C…), repeat structures.

## Output: work/final_pPAGE.json
{"page":PAGE,
 "movements":[{"mvt":"Sinfonia","starts_at":{"sys":S,"x":X}}],   // only if the Sinfonia heading is on this page
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#3","clef":"bass","v":1,"bar":25,
           "dur":"1/4","off":"1/2","tie_from_prev":false,"sim":false,"uncertain":""}, ...],
 "meta":{"bars":[first,last], "meters":[{"bar":1,"meter":"4/4"}], "tempos":[{"bar":1,"text":"Andante","mm":""}],
         "local_bar_count": N, "key_signatures":[{"bar":1,"key":"2 sharps"}],
         "rehearsal":[{"mark":"A","bar":20}], "repeats":"free text: repeat barlines, endings, measure-repeat bars, fermatas, VUOTA blocks"}}
- One entry per played notehead in reading order (system by system, left to right; within a bar, upper-voice notes before lower-voice notes at the same onset is fine — just keep onsets ordered per voice).
- x,y = notehead centre in PAGE pixels (±10 px). dur/off as fractions of a whole note; off = onset from the start of its bar.
- Include the meter in force at the top of the page even if not reprinted there (C = 4/4, ¢ = 2/2).
- Every note must have "bar" (page-local), "dur", "off", "v".
- After writing: run `~/venvs/dynamic/bin/python tools/dynamic/check.py PAGE` and look at all chk images — fix misplaced/missing/extra notes and wrong pitches/voices; then `~/venvs/dynamic/bin/python tools/dynamic/check_rhythm.py PAGE` — fix real errors (cross-voice "overlaps" are already separated by v).

## Then: bar numbers for every bar
Run `~/venvs/dynamic/bin/python tools/dynamic/mk_bars_auto.py PAGE` then view `~/venvs/dynamic/bin/python tools/dynamic/bars_overlay.py PAGE` output (work/barsov_pPAGE_*.png). Write work/bars_pPAGE.json with the same {"sys":[{xa,xb,label}]} structure: fix false barlines (stems are often detected as barlines — merge), add missed ones (split), and give every segment its PAGE-LOCAL bar number; multi-bar rest segments get a range "61–64" (en dash). Every note you listed must fall inside the segment carrying its bar number. Verify with `bars_overlay.py PAGE work/bars_pPAGE.json`.

Reply (structured output): page, note counts per voice (v1, v2, v12), total notes, bars on page (local_bar_count), last local bar, key signatures/meters/tempos found, uncertain count, and a list of issues/uncertain items.
