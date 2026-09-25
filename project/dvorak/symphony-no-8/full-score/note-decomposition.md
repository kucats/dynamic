# Dvořák 8 — full-score note decomposition (trial)

## Verdict

**Feasible.** The same read workflow used for the trombone part works on the
conductor's score once three gaps are closed, all of them solvable:

1. Score staff detection needed a spacing-parameterised detector —
   `tools/dynamic/score_staves.py` (the part detector hard-codes spacings that
   the score's denser staves fail). Verified: pdf p4 → all 16 staves at both
   300 and 600 dpi; pdf p16 → 17 staves in 2 systems.
2. Staff→instrument assignment is **not** fixed — tacet staves are omitted
   (p16 sys 1 = 6 staves, sys 2 = 11). It must be read per system from the
   left-margin names (`--names` crops a strip for exactly this).
3. Shared staves (Ob. I. II., Cl. I. II., Cor, Trbe, Trbni I.II, Fag) write
   two instruments as stem-up/stem-down voices; the `sim` flag already exists
   in the notes schema and reader for stacked tones.

Bar segmentation is already done: `public/score/dvorak8/index.json` carries
reviewed system bands and bar x-positions for all 172 pages / 1108 bars, so a
reader only has to read notes inside existing bar boxes.

## Evidence (tried, not estimated)

- **Staff detection.** `score_staves.py` groups detected staves into systems
  by the reviewed index bands; where a band cuts inside a staff (p16 sys 2
  excluded Fl.I), nearest-band assignment recovered it.
- **Margin names.** p16 sys 2 strip reads Fl. I / Fl. II / Ob. I. II. /
  Cl. I. II. (A) / Cor. I. II. + III. IV. (F) / Viol. I / Viol. II / Vle /
  Vlc / Cb — 11 rows, exactly the detected count.
- **Note read + cross-check.** From the score at 600 dpi, Trbni I.II staff
  (alto clef, same clef the committed part data uses):
  - bar 7 → `Bb3+G3`, `A3+F3` (halves): upper voice = Trombone I `Bb3, A3`,
    lower = Trombone II `G3, F3` — both match the committed part data.
  - bar 9 → `C4+G3` whole dyad = Trombone I `C4` + Trombone II `G3`.
  Written pitch in the score equals written pitch in the parts (trombones
  transpose nothing), so bar-level diffing is direct.

## Method

Per page: `score_staves.py --index …` → per system read margin names →
assign `{instrument, clef, transposition}` per row → per staff run
`score_zoom.py PAGE --staff N --index …` (per-staff guided crop with the
reviewed bar boxes overlaid) → read, tagging stacked notes `sim` → for shared
staves split voices by stem direction → emit either a per-instrument notes
file (same schema as parts) or one score entry keyed by system row.

## Trial read — p4 sys 1, all 16 staves, bars 7–13

Full per-staff census plus note reads on every staff carrying notes
(`trial-p4-sys1.json`):

| Staff | Bars 7–13 |
| --- | --- |
| Fl.I, Fl.II, Ob.I.II, Cor III.IV, Trbe, Trbni III e Tb, Timp, Vl.I, Vl.II | whole-bar rests (9 staves) |
| Cl.I.II.A | sustained figure b7–13 (`♭○`, rest, `●` / `♭○.`+2e / halves / `♭○`+2q) — figure verified against the Drive Cl part; first pitch on ledger C4/B3 flagged `uncertain` (±1 step at this zoom) |
| Fag.I.II | two voices, same figure + moving lower voice |
| Cor.F I.II | same figure a fourth+ higher, `a 2` unison |
| Trbni I.II | **exact match to committed part data** (b7 `Bb3+G3`/`A3+F3`, b8, b9 `C4+G3`) |
| Vle | quarter-dyad + rest punctuation |
| Vlc | sustained bass version of the figure through b13 |
| Cb | quarter-dyad + rest punctuation |

Reading cost for one complete 16-staff system was one detection call + 16
guided crops; rests resolve at first glance, note-bearing staves read at the
same speed as a part page. Residual uncertainty is note-level (±1 step on a
few heads), not structural — the same review pass discipline as the part
audits closes it.

## Score vs parts — where to read the notes

**Recommendation: parts first, score as the verification and projection
layer.** Reasons:

- The 13 same-edition part PDFs are proven input: one instrument context per
  file, no per-system instrument map to read, transposition handled once per
  part instead of per staff, and `zoom.py`/`build_reader.py` run unchanged.
- On the score, every staff additionally needs margin-name assignment per
  system (tacet staves shift the row↔instrument map continuously) — solvable,
  but it is pure overhead compared to reading a file that is already labelled
  CLARINETTO I.
- Same bar content on both sources means the score read is a free audit: read
  score staves at review confidence, diff vs part notes, flag only
  disagreements. That is cheaper than auditing part reads alone.
- If the end goal is notes overlaid on the **score viewer itself**, part
  notes project onto score staves via the shared bar index — the score read
  is then needed only where parts disagree or lack an instrument.

The opposite ordering (score first) is also viable — the trial shows it
works — it just spends the extra effort on instrument-map bookkeeping rather
than notes.

## Data size on the loading side

Measured on what's already committed:

- `public/score/dvorak8/pages/` = **34 MB total, ~200 KB/page WebP**, lazy
  loaded — the score images already open one page at a time; adding notes
  changes nothing about that.
- Part reader JSON embeds cleaned staff crops: `dvorak8-trombone1` = 1.07 MB
  of which ~88% is system images; notes alone are ~0.23 KB/event
  (574 events → 131 KB).

Score note layer estimate: ~1108 bars × ~14 staves × ~50% sounding ×
~4 events ≈ **30k note events → ~2–7 MB JSON total** (≈15–40 KB per page if
split like the page images, ~0.5–1 MB gzipped whole). That is ~5–15% on top
of the existing page payload — no loading concern either way.

Part-data route: 13 parts × ~0.5–3 MB each ≈ **15–30 MB total**, but the
reader loads one instrument at a time, so per-load size stays ~1–3 MB.

Either path is cheap enough that data size should not drive the decision; the
deciding factor is transcription bookkeeping (instrument map + transposition
per staff on the score) vs pipeline reuse (parts).

## What still has to be built / collected

| Item | Status |
| --- | --- |
| Per-system instrument map | ~one margin read per system (layout is stable within sections; verify against detected staff count) |
| Clef inventory | treble / alto / bass covered by guides; **tenor clef guide to add** (Vlc passages, and Trbni I.II in the part uses tenor after bar ~126 — check score) |
| Transpositions for playback | Cl in A, Cor/Trbe in F — written pitch is stored as printed; sounding conversion reuses the HORN_KEYS mechanism generalised to a per-staff key field |
| `build_reader` per-staff filter | today every detected staff becomes a reader system; score parts need `--staff row` (or a `score` entry keeping all rows) |
| Audit corpus | have it: 5 instruments already committed (Tbn I–III, Horn II) **plus all 13 same-edition part PDFs** — see below |

## Source materials (Drive folder `1PxUqddp3Bcd38qZhXwm4sBnNhXeaRXtm`)

- `総譜（Bartoš版）.pdf` — **byte-identical to `Bartos.pdf`** (SHA-256
  `f644a29d…`). Canonical score source; already have it.
- `パート譜（Bartoš版）/` — 13 PDFs covering **every** instrument (Fl; Ob 1·2
  + EH; Cl 1·2; Fag 1·2; Cor 1–4; Trp 1·2; Tbn 1–3 + Tuba; Timp; Vl I; Vl II;
  Vle; Vlc; Cb), same edition family. Double role: (a) the bar-level
  cross-check corpus for score reads, (b) a proven alternate decomposition
  path — they are single-staff pages the existing pipeline already handles.
- `ヴェルディ「ナブッコ」序曲`, `シベリウス「カレリア組曲」` — same
  score+parts structure; the method generalises (Nabucco even ships a
  score variant with printed bar numbers, easing validation).
- Nothing critical is missing: the same-edition parts already give ground
  truth for dense or doubtful pages, so an external MusicXML/OMR reference
  is not required.

## Recommended path

Read the score staves directly (what was asked) and auto-diff each read
against the matching same-edition part — disagreements flag exactly the bars
needing a human look, which is the honest way to reach "完全に分解".
Scale: ~172 pages ≈ 2,700 staff-rows ≈ 3–5 sessions of reading work.

If part-level completeness matters more than the score view itself, the same
pipeline on the 13 part PDFs reaches it faster (parallel per-instrument
sessions, cleaner staves, cues already handled) — the score staves then serve
as the audit target instead of the primary source.

## Caveats recorded during the trial

- Bar 8's accidental looks like the edition's courtesy natural (Eb context);
  old-edition cautionary accidentals need the same `uncertain` discipline as
  the part reads.
- Index bands can clip a staff — trust detection + margin names over the
  band, and record disagreements (p16 sys 2 did this).
- tbn_drive.pdf (トロンボーン1〜3・チューバ, SHA-256 `da7e2e7c…`) is a
  different scan/set than the repo's source `Trombone_1_23Tuba.pdf`
  (`6c161bf1…`) but carries the same content (bars 7–9 structurally equal).
