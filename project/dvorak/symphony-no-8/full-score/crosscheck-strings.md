# Cross-check: strings staves vs part reads (Dvorak 8, mvt I bars 14-27)

- Score side: `full-score/score-notes/p005.json` (PDF p.5 = printed p.3, bars 14-20) and `p006.json` (PDF p.6 = printed p.4, bars 21-27) on `devin/decode-score-p5-6` — the only score-notes decoded so far; the requested page-3-6 scope is covered as far as data exists.
- Part side: `viola/dynamic/pages/notes_p01.json` on `devin/decode-parts-viola`.
- Produced by `work/xcheck-strings/xcheck_strings.py` (gitignored scratch script; reads both branches via `git show`, no merge).
- Pitch convention: as printed (both sides), so viola (alto clef, non-transposing) compares directly; no transposition needed.

## Coverage

| instrument | score staff | part decode | status |
|---|---|---|---|
| Violin I | 12 | none | score read only — cannot cross-check |
| Violin II | 13 | none | score read only — cannot cross-check |
| Viola (Vle) | 14 | `viola/` part | **compared** |
| Cello (Vlc) | 15 | none | score read only — cannot cross-check |
| Contrabass (Cb) | 16 | none | score read only — cannot cross-check |

Only the viola part has been decoded on the supplied part branches (clarinet, horn, trombone, viola). The other four string instruments have no part read to verify against; their score rows are listed below for completeness.

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

(Table shows pitch sets extracted from each staff's `figure` text; "~" marks pitches the score decode flagged uncertain. `rest` = the score decode reports the bar as rests.)

## Viola: score row vs part read

### Bar-number alignment (decode artifact)

The viola part decode labels bars after bar 17 too low, because it counts each printed multimeasure rest as one bar. Verified via the part's own printed numbers (15/20/25/30) and the rehearsal-A letter in the reader system's embedded images:

| part decode label | real (score) bar | evidence |
|---|---|---|
| 14-17 | 14-17 | printed "15" on seg 15 |
| 18 | 18-19 | "2" multimeasure rest counted once |
| 19 | 20-21 | "2" rest, printed "20" at its start |
| 20-24 | 22-26 | arco entrance resumes at real 22 |
| 25 | 27-28 | rest bar + rehearsal-A bar merged into one seg |
| 26 | 29 | |
| 27 | 30 | printed "30" on this seg |
| 28 | 31 | |

All pitch comparisons below use the **real-bar remap**; the naive 1:1 label comparison would show fabricated conflicts starting at bar 18.

### Per-bar pitch sets

| bar | score says | part says (remapped) | verdict |
|---|---|---|---|
| 14 | {D3, F3, G3, Bb3} | {D3, E3, G3, B3, D4, B4} | partial — exact ['G3', 'D3'], ~ ['F3', 'Bb3'], missed [] |
| 15 | {Bb3} | {G3, A3, B3, D4} | partial — exact [], ~ ['Bb3'], missed [] |
| 16 | notes (~) | {C3, E3, G3, A3, B3, D4} | agree — presence (score gave no pitches) |
| 17 | notes (~) | {G3, B3, D4, F4} | agree — presence (score gave no pitches) |
| 18 | rest | {D4, A4} | conflict — score: rest / part: notes |
| 19 | rest | {D4, A4} | conflict — score: rest / part: notes |
| 20 | rest | {D4, A4} | conflict — score: rest / part: notes |
| 21 | rest | {D4, A4} | conflict — score: rest / part: notes |
| 22 | {C4, D4} | {G3, A3, D4, F4} | partial — exact ['D4'], ~ [], missed ['C4'] |
| 23 | {G3, A3, B3} | {G3, B3, D4, F4} | partial — exact ['B3', 'G3'], ~ [], missed ['A3'] |
| 24 | {D3, E3} | {B3, D4, F4} | conflict — no pitch overlap (missed ['D3', 'E3']) |
| 25 | rest | {D4, A4} | conflict — score: rest / part: notes |
| 26 | rest | {G3, B3, F4} | conflict — score: rest / part: notes |
| 27 | rest | {E3, G3, B3, D4, F4, A4, B4} | conflict — score: rest / part: notes |

## Disagreements

| bar | instrument | score says | part says | severity / cause |
|---|---|---|---|---|
| 14 | Vle | {D3, F3, G3, Bb3} | {D3, E3, G3, B3, D4, B4} | medium — some pitches differ: exact ['G3', 'D3'], ~ ['F3', 'Bb3'], missed [] |
| 15 | Vle | {Bb3} | {G3, A3, B3, D4} | medium — some pitches differ: exact [], ~ ['Bb3'], missed [] |
| 18 | Vle | rest | {D4, A4} | medium — false-positive notes read on the "2" rest glyph (image: whole rests): score: rest / part: notes |
| 19 | Vle | rest | {D4, A4} | medium — false-positive notes read on the "2" rest glyph (image: whole rests): score: rest / part: notes |
| 20 | Vle | rest | {D4, A4} | medium — false-positive notes read on the "2" rest glyph (image: whole rests): score: rest / part: notes |
| 21 | Vle | rest | {D4, A4} | medium — false-positive notes read on the "2" rest glyph (image: whole rests): score: rest / part: notes |
| 22 | Vle | {C4, D4} | {G3, A3, D4, F4} | medium — some pitches differ: exact ['D4'], ~ [], missed ['C4'] |
| 23 | Vle | {G3, A3, B3} | {G3, B3, D4, F4} | medium — some pitches differ: exact ['B3', 'G3'], ~ [], missed ['A3'] |
| 24 | Vle | {D3, E3} | {B3, D4, F4} | high — real pitch conflict on a sounded bar; part-image supports the score's low note below staff: no pitch overlap (missed ['D3', 'E3']) |
| 25 | Vle | rest | {D4, A4} | medium — false-positive notes read on the "1" rest glyph (image: whole rest): score: rest / part: notes |
| 26 | Vle | rest | {G3, B3, F4} | medium — timpani cue-note pitches filed as viola notes (part: rest + cue): score: rest / part: notes |
| 27 | Vle | rest | {E3, G3, B3, D4, F4, A4, B4} | medium — merged seg: part notes include the real-28 rehearsal-A entrance (real 27 is rest+cue): score: rest / part: notes |

## Adjudication via the part's embedded images

The viola reader data embeds cropped system images; inspecting the four systems covering bars 13-31 confirms which read is right where the two decodes disagree:

- **b14**: image shows pizz dyads {G3+D3} then a flat-marked {Bb3+F3} — score right; the part decode read the second dyad {E3,G3}.
- **b15**: image shows one flat-marked dyad + rests — consistent with the score's ~Bb3 claim; part decode's {G3,B3,A3,D4} misses the flat.
- **b17**: image shows one dyad + rests — both sides have notes.
- **b18-21**: image shows two "2" multimeasure rests — the viola really does rest; every part note in these bars is a false positive.
- **b22-24**: image shows the arco entrance (pp): bar of rests ending in an 8th note, then a half note + 8th-note bar, then a low note below the staff + rest — matching the score's b22-24 figure; the part decode splits the same image but assigns the notes to labels 20-22 and adds extra heads.
- **b25-27**: image shows a "1" rest (printed 25) then two rest bars carrying a timpani cue, then the rehearsal-A entrance — the viola rests through real 27 as the score says.

## Notes

- **Rest-region false positives (part decode).** In the real-bar rests (18-21, 25) the part decode still emits notes — black blobs on the multimeasure-rest glyphs were read as noteheads (`uncertain: auto` on all of them). Musical content is rests on both sides.
- **Cue notes read as viola notes (part decode).** Real bars 26-27 are rest + timpani cue in the part; the decode filed the cue pitches as viola notes.
- **Merged segment.** The part decode's seg for label 25 merges the real-bar-27 rest/cue bar and the real-bar-28 rehearsal-A entrance into one segment; its pitch set mixes the two bars.
- **Score read is low-confidence too.** Every string `figure` in the score-notes is flagged `uncertain`; pitch-zone qualifiers (~, "X/Y") were widened to candidate sets for matching. A score pitch matching a part pitch within one semitone is reported as '~', not exact.
- **Coverage gap.** Violin I/II, cello, contrabass have no decoded parts on any branch; their score rows above are unverified by this check. A future part decode (or the score crop images) is needed to finish the strings scope.
- Verdicts: `agree` = all claimed score pitches matched exactly (or both sides rest / both sides have notes where the score gave no pitches); `partial` = some exact, rest only ~ or missed; `conflict` = rest-vs-notes or zero overlap.

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

