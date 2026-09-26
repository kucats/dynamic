# Cross-check: strings staves vs part reads (Dvorak 8, mvt I bars 14-27)

- Score side: `full-score/score-notes/p005.json` (PDF p.5 = printed p.3, bars 14-20) and `p006.json` (PDF p.6 = printed p.4, bars 21-27) on `devin/decode-score-p5-6` — the only score-notes decoded so far; the requested page-3-6 scope is covered as far as data exists.
- Part side: `notes_p01.json` + `bars_p01.json` on `devin/decode-parts-violin2`, `-viola`, `-cello`, `-bass` (all read-only via `git show`, no merge).
- Diff produced by `work/xcheck-strings/xcheck_strings.py` (gitignored scratch; reads both branches via `git show`).
- Pitch convention: `pitch as printed` on both sides, so all five string instruments compare directly — viola is alto clef in both part and score (score clefs map: 14 alto, 15/16 bass), and Cb is written pitch on both sides. No transposition adjustment needed.
- Adjudication uses the score page images `public/score/dvorak8/pages/p005.webp` / `p006.webp` and the part system strips embedded in `public/reader/data/dvorak8-{violin2,viola,contrabass}.json` (no cello reader JSON exists, so cello is adjudicated only via the score image).

## Coverage

| instrument | score staff | part decode | status |
|---|---|---|---|
| Violin I | 12 | **none** | score read only — cannot cross-check |
| Violin II | 13 | `violin-ii/` | compared (labels ≈ real bars, ±1 boundary drift) |
| Viola (Vle) | 14 | `viola/` | compared (labels remapped — multimeasure rests counted once) |
| Cello (Vlc) | 15 | `cello/` | compared (labels = real bars) |
| Contrabass (Cb) | 16 | `contrabass/` | compared (labels = real bars) |

`Violin I` has no decoded part on any supplied part branch — the single biggest coverage gap; its score row below is unverified by this check.

## Score string-staff reads (as decoded)

| bar | Viol.I | Viol.II | Vle | Vlc | Cb |
|---|---|---|---|---|---|
| 14 | rest | rest | {D3, F3, G3, Bb3} | {Bb3, B3} | {G3, Eb4} |
| 15 | rest | rest | {Bb3} | {C4, D4} | {B3, D4} |
| 16 | rest | rest | notes (pitches ~) | {C4, D4} | {B3, D4} |
| 17 | {D5} | {B4} | notes (pitches ~) | {C4, D4} | {G3} |
| 18 | {D5} | {B4} | rest | {C4, D4} | rest |
| 19 | {D5, E5} | {D5} | rest | rest | rest |
| 20 | rest | rest | rest | rest | rest |
| 21 | rest | rest | rest | rest | rest |
| 22 | {A4, B4} | {F4, G4} | {C4, D4} | rest | rest |
| 23 | {C5, D5} | {F4, G4, A4} | {G3, A3, B3} | rest | rest |
| 24 | {D5} | {G4, A4} | {D3, E3} | {G2, B2, C4, D4} | {F3, G3, C4, D4} |
| 25 | rest | rest | rest | {G2, A2, D3, E3} | {G2, A2, D3, E3} |
| 26 | rest | rest | rest | rest | rest |
| 27 | rest | rest | rest | rest | rest |

(Pitch sets extracted from each staff's `figure` text; "~" marks pitches the score decode flagged uncertain. `rest` = score decode reports the bar as rests. `notes (~)` = decode saw noteheads but gave no pitch.)

## Bar-number alignment

| part | labels → real bars | evidence |
|---|---|---|
| Violin II | labels = real, ±1 px-boundary drift | printed "20"/"25"/"30" and rehearsal "A"(=28) all land on the decode's same-numbered segs; vn entrance at seg 17 matches score (pp tied dyad) |
| Viola | label 18→18-19; 19→20-21; 20-24→22-26; 25→27-28 (merged); 26→29; 27→30; 28→31 | decode counts each printed multimeasure rest as one bar; verified vs printed 15/20/25/30 + rehearsal A (prior adjudication) |
| Cello | labels = real | part meta verified bar grid vs printed every-5 numbers; 5-bar rest run 19-23 agrees with score both sides |
| Contrabass | labels = real | ranged rest labels ("18–19","20–23") already group multimeasure rests; opening pizz matches score pitches exactly |

## Per-bar comparison

| bar | instr | score says | part says | verdict |
|---|---|---|---|---|
| 14 | Vl.II | rest | {B5, C5} | conflict — cue-note bleed (see notes) |
| 15 | Vl.II | rest | {D4, E5} | conflict — cue-note bleed |
| 16 | Vl.II | rest | {B4, C5} | conflict — cue-note bleed |
| 17 | Vl.II | {B4} | rest | conflict — part decode omission (image: tied dyad present) |
| 18 | Vl.II | {B4} | rest | conflict — part decode omission (image: tied dyad present) |
| 19 | Vl.II | {D5} | {A4} | conflict — pitch (image: tied dyad continues; both reads approximate) |
| 20 | Vl.II | rest | {A4, C5} | conflict — **score omission** (image: quarter dyad + rests at b20) |
| 21 | Vl.II | rest | rest | agree |
| 22 | Vl.II | {F4, G4} | {C5} | conflict — image confirms score's ~G4/F4 8th; part pitch wrong |
| 23 | Vl.II | {A4, F4, G4} | {A4, C5, E5} | partial — exact ['A4'] (the ~A4/G4 half); part adds {C5,E5} |
| 24 | Vl.II | {A4, G4} | {A4, C5, F4} | partial — exact ['A4'] |
| 25 | Vl.II | rest | {E5, F4} | conflict — part false positives on "25" rest region |
| 26 | Vl.II | rest | rest | agree |
| 27 | Vl.II | rest | {C5, F5} | conflict — part false positives on "3"-multimeasure-rest region |
| 14 | Vle | {D3, F3, G3, Bb3} | {B3, B4, D3, D4, E3, G3} | partial — exact ['D3','G3'], ~ ['Bb3','F3'] |
| 15 | Vle | {Bb3} | {A3, B3, D4, G3} | partial — ~ ['Bb3'] |
| 16 | Vle | notes | {A3, B3, C3, D4, E3, G3} | agree — presence (score gave no pitches) |
| 17 | Vle | notes | {B3, D4, F4, G3} | agree — presence |
| 18 | Vle | rest | {A4, D4} | conflict — part false positives on "2"-rest glyph |
| 19 | Vle | rest | {A4, D4} | conflict — same |
| 20 | Vle | rest | {A4, D4} | conflict — same |
| 21 | Vle | rest | {A4, D4} | conflict — same |
| 22 | Vle | {C4, D4} | {A3, D4, F4, G3} | partial — exact ['D4'], missed ['C4'] |
| 23 | Vle | {G3, A3, B3} | {B3, D4, F4, G3} | partial — exact ['B3','G3'], missed ['A3'] |
| 24 | Vle | {D3, E3} | {B3, D4, F4} | conflict — image confirms score's ~E3/D3 below staff; part pitches wrong |
| 25 | Vle | rest | {A4, D4} | conflict — part false positives on "1"-rest glyph |
| 26 | Vle | rest | {B3, F4, G3} | conflict — part filed timpani-cue pitches as viola notes |
| 27 | Vle | rest | {A4, B3, B4, D4, E3, F4, G3} | conflict — merged seg mixes real-27 rest/cue with real-28 reh.-A entrance |
| 14 | Vlc | {Bb3, B3} | {Bb3, C4} | partial — exact ['Bb3'], ~ ['B3' vs 'C4'] |
| 15 | Vlc | {C4, D4} | {D4} | partial — part matches principal pitch; score's extra ~C4 dubious |
| 16 | Vlc | {C4, D4} | {D4} | partial — same |
| 17 | Vlc | {C4, D4} | {D4} | partial — same |
| 18 | Vlc | {C4, D4} | {D4} | partial — same |
| 19 | Vlc | rest | rest | agree |
| 20 | Vlc | rest | rest | agree |
| 21 | Vlc | rest | rest | agree |
| 22 | Vlc | rest | rest | agree |
| 23 | Vlc | rest | rest | agree |
| 24 | Vlc | {B2, C4, D4, G2} | {A3} | conflict — presence yes (real: 8th + open half); pitch disputed |
| 25 | Vlc | {A2, D3, E3, G2} | {C4, D4} | conflict — score's pitch set partly belongs to real bar 26 (misassignment) |
| 26 | Vlc | rest | {D4} | conflict — **score error** (image: dotted dyad ~{F3, C4-ish} at b26; part right) |
| 27 | Vlc | rest | rest | agree |
| 14 | Cb | {Eb4, G3} | {Eb4, G3} | agree — exact ['Eb4','G3'] |
| 15 | Cb | {B3, D4} | {D4} | partial — part dropped the ~B3 |
| 16 | Cb | {B3, D4} | {D4} | partial — same |
| 17 | Cb | {G3} | {G3} | agree — exact |
| 18 | Cb | rest | rest | agree |
| 19 | Cb | rest | rest | agree |
| 20 | Cb | rest | rest | agree |
| 21 | Cb | rest | rest | agree |
| 22 | Cb | rest | rest | agree |
| 23 | Cb | rest | rest | agree |
| 24 | Cb | {C4, D4, F3, G3} | {E4} | conflict — real b24 8th is ~B3/C4-ish; part's E4 likely same note misread |
| 25 | Cb | {A2, D3, E3, G2} | {A3} | conflict — part's A3 ≈ real open half at b25 (score assigned it to end of b24) |
| 26 | Cb | rest | {D3} | conflict — **score error** (image: dotted ~D3 note at b26; part right) |
| 27 | Cb | rest | rest | agree |

Mechanical tally: **56 bar×instrument comparisons, 19 exact agreements** (plus 14 Vl.I rows unverifiable — no part). Partial = score and part share ≥1 exact or semitone-adjacent pitch; conflict = rest-vs-notes or zero overlap. Per-bar detail text from the diff script follows the same convention as before: `~` = score pitch matched within one semitone of a part pitch, `missed` = score pitch with no part counterpart.

## Disagreements and adjudication

Where the two decodes disagree, the score page images and the part's own embedded system strips decide which side (if either) is right.

### Violin II (labels = real bars; "20"/"25"/"30"/reh-A anchors verified)

| bar | score says | part says | severity / cause |
|---|---|---|---|
| 14-16 | rest | {B5,C5} / {D4,E5} / {B4,C5} | low — printed Vlc cue notes (small heads, `unc` on every note) read as vn2 notes; vn2 really rests |
| 17 | {B4} | rest | medium — part decode omission: its own image shows the tied open-head dyad (B4+D5, pp) entering at 17 |
| 18 | {B4} | rest | medium — same omission; tied dyad continues |
| 19 | {D5} | {A4} | medium — image: dyad still tied (no new quarter); score's "new D5" and part's lone A4 are both approximations |
| 20 | rest | {A4, C5} | medium — **score omission**: image shows a quarter-note dyad + rests at b20; part pitches ~a 2nd low (real ≈ B4/D5) |
| 22 | {F4, G4} | {C5} | medium — image confirms [half rest][8th rest][~G4 8th]; part's C5 is wrong (~4th high) |
| 23 | {F4, G4, A4} | {A4, C5, E5} | low — exact on the half (~A4/G4 — part's A4 may be the right call); part adds {C5, E5} from split heads |
| 24 | {A4, G4} | {A4, C5, F4} | low — exact on A4; extras again |
| 25 | rest | {E5, F4} | low — part false positives inside the "25" whole-rest bar |
| 27 | rest | {C5, F5} | low — part false positives inside the "3" multimeasure-rest bar |

### Viola (labels remapped per alignment table)

Verdicts and image adjudication are unchanged from the earlier viola-only pass: b14-15 partial (score's flat-marked dyads confirmed; part missed flats), b16-17 presence-agree, b18-21 and b25 conflicts adjudicated to part false positives on multimeasure-rest glyphs, b22-23 partial (arco entrance; part over-segments into extra heads), **b24 conflict stands: score image shows the ~E3/D3 open half below the staff — part's {B3,D4,F4} is wrong**, b26-27 conflicts adjudicated to timpani-cue bleed and the label-25 seg merging real 27+28.

| bar | score says | part says (remapped) | severity / cause |
|---|---|---|---|
| 14 | {D3, F3, G3, Bb3} | {B3, B4, D3, D4, E3, G3} | medium — part missed flats (Bb3~B3, F3 read E3-adjacent); image favors score |
| 15 | {Bb3} | {A3, B3, D4, G3} | medium — flat missed again |
| 18-21 | rest | {A4, D4} | medium — false positives on "2"-rest glyphs |
| 22 | {C4, D4} | {A3, D4, F4, G3} | medium — missed C4, extra heads |
| 23 | {G3, A3, B3} | {B3, D4, F4, G3} | medium — missed A3, extra heads |
| 24 | {D3, E3} | {B3, D4, F4} | high — real pitch conflict; image supports score's below-staff note |
| 25 | rest | {A4, D4} | medium — false positives on "1"-rest glyph |
| 26 | rest | {B3, F4, G3} | medium — timpani cue pitches filed as viola |
| 27 | rest | {A4, B3, B4, D4, E3, F4, G3} | medium — seg merge pulls in real-28 entrance |

### Cello (labels = real bars; 19-23 rest on both sides anchors the grid)

| bar | score says | part says | severity / cause |
|---|---|---|---|
| 14 | {Bb3, B3} | {Bb3, C4} | low — Bb3 exact; the tied B-flat→natural resolution split as B3 vs C4 (semitone apart) |
| 15-18 | {C4, D4} | {D4} | low — part reads only the principal pitch; score's extra ~C4 is a candidate-set widening, likely one real note per bar |
| 24 | {B2, C4, D4, G2} | {A3} | medium — real bar = 8th + open half; part caught one note at wrong pitch |
| 25 | {A2, D3, E3, G2} | {C4, D4} | medium — score's set lumps in real-26 content (see b26); part pitches plausible for the real-25 open half + 8th |
| 26 | rest | {D4} | **high — score decode error**: image shows a dotted open dyad (~{F3, C4/B3}) in bar 26; the score read it into its "b25" figure and reported 26 as rest. Part right on presence, ~right on pitch |

### Contrabass (labels = real bars; ranged rest labels verified)

| bar | score says | part says | severity / cause |
|---|---|---|---|
| 15-16 | {B3, D4} | {D4} | low — part dropped the lower ~B3 of each bar |
| 24 | {C4, D4, F3, G3} | {E4} | medium — real b24 = rests + one 8th (~B3/C4-ish); part's E4 is a plausible misread of that head; score's set also includes the real-25 open half |
| 25 | {A2, D3, E3, G2} | {A3} | medium — image shows an open half ~A3 at b25: part plausibly right on pitch, wrong-bar on the score side (score put it at "end of b24" as ~C4/D4) |
| 26 | rest | {D3} | **high — score decode error**: image shows a dotted ~D3 note in bar 26 (D3 line); part exactly right |

## Notes

- **Systematic score misassignment at p6 b25-26 (Vlc + Cb).** The score decode's "b25" figure actually describes real b25's tail **plus** real b26's dotted note, and it reports b26 as a rest. Both parts independently show a note at 26 — corroborated by the score image. Likely cause: the open half at the start of real 25 was absorbed into "b24"'s figure, shifting the remaining events one bar early. This is the most consequential finding: a bar-grid error in the score decode, not a pitch error.
- **Part-decode failure modes.** (a) open/whole-head noteheads on quiet tied notes are silently dropped (vn2 17-18); (b) rest glyphs (whole/half/multimeasure) are read as noteheads, producing false-positive pitch sets in rest bars (vn2 25/27; viola 18-21/25); (c) printed cue notes (small heads) are filed as real notes even though flagged `unc` (vn2 14-16; viola 26-27); (d) noteheads near interpolated bar boundaries can land ±1 bar off (vn2 grid is uniform-interpolated, deviating up to ~half a bar from detected barlines).
- **Score read is low-confidence too.** Every string `figure` carries `uncertain`; "~"/"X/Y" were widened to candidate sets, so a "partial" verdict can be a correct read matching the score's own uncertainty band (e.g. vn2 A4 inside the score's ~A4/G4).
- **Unverified coverage.** Violin I (staff 12) has no part decode at all; cello pitches could not be cross-adjudicated against a part image (no reader JSON for `dvorak8-cello` exists on the part branch).
- Verdicts: `agree` = all claimed score pitches matched (or both rest / both notes where score gave no pitches); `partial` = ≥1 exact or ~ match; `conflict` = rest-vs-notes or zero overlap.

Score figure text for reference (verbatim):

- p5 Viol.I (bars 14-20): b17 [half rest][~D5 half, slur, pp]; b18 [~D5 half][~D5 half] (tie/slur over both); b19 [~D5/E5 filled quarter][quarter rest][half rest]; b14-16,20 rests
- p5 Viol.II (bars 14-20): b17 [half rest][~B4 half, slur, pp]; b18 [~B4 half][~B4 half]; b19 [~D5 quarter][rests]; b14-16,20 rests — mirrors Viol.I a third lower ({B4+D5} held dyad)
- p5 Vle (bars 14-20): alto clef divisi pizz dyad 8ths, echoing Cb: b14 [{G3+D3} 8th][rest][{Bb3+F3} 8th w/ flat][rest]; b15 [8th rest][~B3-ish 8th w/ flat-ish][8th rest][half rest]; b16 ~3 dyad 8ths + rests; b17 ~1-2 dyads + half rest; b18-20 rests
- p5 Vlc (bars 14-20): b14 [Bb3 half w/ flat][Bb3/B3 half] slurred; b15-17 ~D4 whole each (C4/D4 boundary; ppp at 17); b18 ~D4 quarter + quarter rest + half rest; b19-20 rests
- p5 Cb (bars 14-20): bass clef pizz 8th-note punctuation: b14 [G3 8th][8th rest][Eb4-ish 8th w/ flat][8th rest]; b15 [~B3 8th][rest][~D4 8th][rest]; b16 same shape (~B3 / ~D4); b17 [~G3 8th][8th rest][half rest]; b18-20 rests
- p6 Viol.I (bars 21-27): b22 [half rest][8th rest][~B4/A4 8th] pp; b23 [~D5 half][8th rest][~C5 8th]; b24 [~D5 half][half rest]; b21, b25-27 rests
- p6 Viol.II (bars 21-27): b22 [half rest][8th rest][~G4/F4 8th]; b23 [~A4/G4 half][8th rest][~G4/F4 8th]; b24 [~A4/G4 half][half rest]; b21, b25-27 rests — mirrors Viol.I ~a third lower
- p6 Vle (bars 21-27): 'arco' marked at b22. b22 [half rest][8th rest][~D4/C4 8th] pp; b23 [~B3/A3 half][8th rest][~A3/G3 8th]; b24 [~E3/D3 half, below staff][half rest]; b21, b25-27 rests
- p6 Vlc (bars 21-27): b24 [half rest][8th rest][~B2/G2 8th][~C4/D4 open half-ish at bar end]; b25 [8th rest][~E3/D3 8th][~A2/G2 dotted open note]; b21-23, b26-27 rests
- p6 Cb (bars 21-27): b24 [half rest][8th rest][~G3/F3 8th][~C4/D4 open half-ish]; b25 [8th rest][~E3/D3 8th][~A2/G2 dotted open note]; b21-23, b26-27 rests — same figure shape as Vlc up ~an octave/steps
