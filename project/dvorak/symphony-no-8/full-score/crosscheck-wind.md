# Dvořák 8 mvt I — score-staff vs part cross-check: winds & brass

Scope: score PDF pages 4–6 (system 1 each = bars 7–13 trial, 14–20, 21–27) — the only score reads on `devin/decode-score-p5-6`. PDF p3 (bars 1–6) has no score-notes file yet.

**Convention:** both sides store written pitch, so comparison is direct — Cl in A, Cor/Trbe in F, Cb −8ve cancel written-vs-written. Trbni I.II is alto clef on the score and in the committed trombone part data.

Part reads used: clarinet-i/ii, horn-i…iv (horn branch), trombone-i (main), tuba (trombone branch). **Missing part decodes**: flute-i/ii, oboe-i/ii, bassoon-i/ii, trumpet-i/ii, trombone-ii, trombone-iii — rows 1,2,3,5,8 and the lower voices of rows 9–10 are unverifiable.

Uncertainty: score `uncertain` flags / `~` `-ish` `/` reads; part `unc` flags incl. `auto-draft` / `auto-decode` / `bar estimated`; `cue` notes excluded.

**Result: 105 staff-bar cells compared, 72 agree, 31 disagreements.**


## Notable patterns

- **HIGH — likely score miss at b26–27 (staff 10 Trbni III e Tb).** Score marks the row all-rest b21–27, but the tuba part has clean unflagged `D2` whole notes at b26–30, and the score's own timpani read catches a `D3` roll at b26–27 — the tuba D pedal (and probably Trbni III with it) was missed on the score read.
- **Cl.I.II staff: score reads sit ~1 step from part reads in both decoded windows.** Trial (b7–13) keeps the pitch field at `{C4,Cb4,Db4}` vs clarinet-i's confirmed `Db4`-with-flat line (partial match, score ambiguity range covers it); p005 reads `Eb4` b14–18 vs parts `{cl-i: D4→F4, cl-ii: G4→D4}` — disjoint, but the figure shape/rhythm matches. Score row flagged `uncertain` throughout; needs a zoom re-pass rather than a re-decode.
- **Cor.F I.II trial (b7–13): pitch-zone estimate `{C5,D5}` vs parts' `{F4,Bb4,C5}`** — rhythm/figure confirmed same-as-Cl shape, score pitch zone off by ~a fourth and flagged `uncertain`. p005's structured re-read of the same staff verified exactly vs committed horn data, so this is a trial-quality artifact.
- **Cor.F III.IV b16–26: cluster of auto-draft part notes vs asserted score rests** (horn-iii `A4×2`, `G4`, `G5`; horn-iv `F4`,`G4`,`A3`,`F3`,`C4`,`E4`). Part reads are all `auto-draft`/`bar estimated` quality and several pitches are implausible for the register — likely misread glyphs, but this row also carries the tuba miss above, so it deserves one eyeball pass. Note horn-iv's `bar estimated` `A3`(b19) vs score's low-voice `A3`(b17) could be the same note with a ±2 bar drift.
- **Verified anchors hold**: score's structured rows verified against committed parts reproduce exactly — Cor.F I.II b14–18 (horn-i=horn-ii 'a 2'), Trbni I.II upper voice b7–18 (trombone-i), tuba F1 b17–18 (score `F1-ish` lower voice).


## Coverage matrix (per staff row × bar)

| staff | instrument | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Fl.I | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| 2 | Fl.II | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| 3 | Ob.I.II | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| 4 | Cl.I.II.A | × | × | × | × | × | ~ | × | × | × | ~ | ~ | × | ? | ? | ✓ | ✓ | ✓ | ✓ | × | ✓ | ✓ |
| 5 | Fag.I.II | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| 6 | Cor.F I.II | × | × | × | × | × | × | × | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 7 | Cor.F III.IV | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | × | ~ | × | × | × | × | × | ✓ | × | ✓ | × | ✓ |
| 8 | Trbe I.II.F | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| 9 | Trbni I.II | ◦ | ◦ | ◦ | ✓ | ✓ | ✓ | ✓ | ◦ | ◦ | ◦ | ◦ | ◦ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 10 | Trbni III e Tb | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ◦ | ◦ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |

✓ agree · ◦ agree modulo missing part voice · ✗ diff (high) · × diff (medium) · ~ diff (low) · ? score unstated · `·` no part read


## Disagreements

| page | bar | staff | score says | part says | severity | notes |
|---|---|---|---|---|---|---|
| p4 | 7 | Cl.I.II.A | {C4,Cb4,Db4} | clarinet-i=Db4;clarinet-ii=A3,D4 | medium | score-uncertain |
| p4 | 8 | Cl.I.II.A | {C4,Cb4,Db4} | clarinet-i=Db4,E4,F4;clarinet-ii=rest | medium | score-uncertain |
| p4 | 9 | Cl.I.II.A | {C4,Cb4,Db4} | clarinet-i=G4;clarinet-ii=rest | medium | score-uncertain |
| p4 | 10 | Cl.I.II.A | {C4,Cb4,Db4} | clarinet-i=A4,C4;clarinet-ii=B4,D4,E4,E5,F4 | medium | score-uncertain |
| p4 | 11 | Cl.I.II.A | {C4,Cb4,Db4} | clarinet-i=G4,Gb4;clarinet-ii=G4 | medium | score-uncertain |
| p4 | 12 | Cl.I.II.A | {C4,Cb4,Db4} | clarinet-i=Gb4;clarinet-ii=A4,B4,G4 | low | score-uncertain part-uncertain |
| p4 | 13 | Cl.I.II.A | {C4,Cb4,Db4} | clarinet-i=E4,F4,Gb4;clarinet-ii=B3,G4 | medium | score-uncertain |
| p5 | 14 | Cl.I.II.A | {Eb4} | clarinet-i=D4,G5;clarinet-ii=G4 | medium | score-uncertain |
| p5 | 15 | Cl.I.II.A | {Eb4} | clarinet-i=F4;clarinet-ii=F4,G4 | medium | score-uncertain |
| p5 | 16 | Cl.I.II.A | {Eb4} | clarinet-i=F4;clarinet-ii=E4 | low | score-uncertain part-uncertain |
| p5 | 17 | Cl.I.II.A | {Eb4} | clarinet-i=F4;clarinet-ii=D4 | low | score-uncertain part-uncertain |
| p5 | 18 | Cl.I.II.A | {Eb4} | rest | medium | score-uncertain |
| p6 | 25 | Cl.I.II.A | rest | clarinet-i=rest;clarinet-ii=C4 | medium | part-uncertain |
| p4 | 7 | Cor.F I.II | {C5,D5} | horn-i=F4;horn-ii=F4 | medium | score-uncertain |
| p4 | 8 | Cor.F I.II | {C5,D5} | horn-i=A4,F4,G4;horn-ii=A4,F4,G4 | medium | score-uncertain |
| p4 | 9 | Cor.F I.II | {C5,D5} | horn-i=Bb4;horn-ii=Bb4 | medium | score-uncertain |
| p4 | 10 | Cor.F I.II | {C5,D5} | horn-i=Bb4,C5;horn-ii=Bb4,C5 | medium | score-uncertain |
| p4 | 11 | Cor.F I.II | {C5,D5} | horn-i=Bb4;horn-ii=Bb4 | medium | score-uncertain |
| p4 | 12 | Cor.F I.II | {C5,D5} | horn-i=Bb4;horn-ii=Bb4 | medium | score-uncertain |
| p4 | 13 | Cor.F I.II | {C5,D5} | horn-i=A4,Bb4,G4;horn-ii=A4,Bb4,G4 | medium | score-uncertain |
| p5 | 16 | Cor.F III.IV | rest | horn-iii=rest;horn-iv=F4 | medium | part-uncertain |
| p5 | 17 | Cor.F III.IV | {A3} | horn-iii=rest;horn-iv=G4 | low | score-uncertain part-uncertain |
| p5 | 18 | Cor.F III.IV | {A3} | rest | medium | score-uncertain |
| p5 | 19 | Cor.F III.IV | rest | horn-iii=G4;horn-iv=A3 | medium | part-uncertain |
| p5 | 20 | Cor.F III.IV | rest | horn-iii=G5;horn-iv=rest | medium | part-uncertain |
| p6 | 21 | Cor.F III.IV | rest | horn-iii=A4;horn-iv=rest | medium | part-uncertain |
| p6 | 22 | Cor.F III.IV | rest | horn-iii=rest;horn-iv=F3 | medium | part-uncertain |
| p6 | 24 | Cor.F III.IV | rest | horn-iii=A4;horn-iv=C4 | medium | part-uncertain |
| p6 | 26 | Cor.F III.IV | rest | horn-iii=rest;horn-iv=E4 | medium | part-uncertain |
| p6 | 26 | Trbni III e Tb | rest | tuba=D2 | high | no part: trombone-iii |
| p6 | 27 | Trbni III e Tb | rest | tuba=D2 | high | no part: trombone-iii |


## Detail dump

| page | bar | staff | verdict | score | parts | flags |
|---|---|---|---|---|---|---|
| p4 | 7 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p4 | 8 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p4 | 9 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p4 | 10 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p4 | 11 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p4 | 12 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p4 | 13 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p5 | 14 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p5 | 15 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p5 | 16 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p5 | 17 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p5 | 18 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p5 | 19 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p5 | 20 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p6 | 21 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p6 | 22 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p6 | 23 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p6 | 24 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p6 | 25 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p6 | 26 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p6 | 27 | Fl.I | no-part-read | - | - | info no part decode for flute-i |
| p4 | 7 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p4 | 8 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p4 | 9 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p4 | 10 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p4 | 11 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p4 | 12 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p4 | 13 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p5 | 14 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p5 | 15 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p5 | 16 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p5 | 17 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p5 | 18 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p5 | 19 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p5 | 20 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p6 | 21 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p6 | 22 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p6 | 23 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p6 | 24 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p6 | 25 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p6 | 26 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p6 | 27 | Fl.II | no-part-read | - | - | info no part decode for flute-ii |
| p4 | 7 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p4 | 8 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p4 | 9 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p4 | 10 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p4 | 11 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p4 | 12 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p4 | 13 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p5 | 14 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p5 | 15 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p5 | 16 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p5 | 17 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p5 | 18 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p5 | 19 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p5 | 20 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p6 | 21 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p6 | 22 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p6 | 23 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p6 | 24 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p6 | 25 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p6 | 26 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p6 | 27 | Ob.I.II | no-part-read | - | - | info no part decode for oboe-i,oboe-ii |
| p4 | 7 | Cl.I.II.A | DIFF partial∩{Db4} | {C4,Cb4,Db4} | {A3,D4,Db4} | medium  scoreUnc |
| p4 | 8 | Cl.I.II.A | DIFF partial∩{Db4} | {C4,Cb4,Db4} | {Db4,E4,F4} | medium  scoreUnc |
| p4 | 9 | Cl.I.II.A | DIFF disjoint | {C4,Cb4,Db4} | {G4} | medium  scoreUnc |
| p4 | 10 | Cl.I.II.A | DIFF partial∩{C4} | {C4,Cb4,Db4} | {A4,B4,C4,D4,E4,E5,F4} | medium  scoreUnc |
| p4 | 11 | Cl.I.II.A | DIFF disjoint | {C4,Cb4,Db4} | {G4,Gb4} | medium  scoreUnc |
| p4 | 12 | Cl.I.II.A | DIFF disjoint | {C4,Cb4,Db4} | {A4,B4,G4,Gb4} | low  scoreUnc partUnc |
| p4 | 13 | Cl.I.II.A | DIFF disjoint | {C4,Cb4,Db4} | {B3,E4,F4,G4,Gb4} | medium  scoreUnc |
| p5 | 14 | Cl.I.II.A | DIFF disjoint | {Eb4} | {D4,G4,G5} | medium  scoreUnc |
| p5 | 15 | Cl.I.II.A | DIFF disjoint | {Eb4} | {F4,G4} | medium  scoreUnc |
| p5 | 16 | Cl.I.II.A | DIFF disjoint | {Eb4} | {E4,F4} | low  scoreUnc partUnc |
| p5 | 17 | Cl.I.II.A | DIFF disjoint | {Eb4} | {D4,F4} | low  scoreUnc partUnc |
| p5 | 18 | Cl.I.II.A | DIFF: part=rest, score notes | {Eb4} | rest | medium  scoreUnc |
| p5 | 19 | Cl.I.II.A | unstated (score silent on bar) | unstated | rest | info  |
| p5 | 20 | Cl.I.II.A | score unstated, part has notes | unstated | {F4} | low  partUnc |
| p6 | 25 | Cl.I.II.A | DIFF: score=rest, part notes | rest | {C4} | medium  partUnc |
| p4 | 7 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p4 | 8 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p4 | 9 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p4 | 10 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p4 | 11 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p4 | 12 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p4 | 13 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p5 | 14 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p5 | 15 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p5 | 16 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p5 | 17 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p5 | 18 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p5 | 19 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p5 | 20 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p6 | 21 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p6 | 22 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p6 | 23 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p6 | 24 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p6 | 25 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p6 | 26 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p6 | 27 | Fag.I.II | no-part-read | - | - | info no part decode for bassoon-i,bassoon-ii |
| p4 | 7 | Cor.F I.II | DIFF disjoint | {C5,D5} | {F4} | medium  scoreUnc |
| p4 | 8 | Cor.F I.II | DIFF disjoint | {C5,D5} | {A4,F4,G4} | medium  scoreUnc |
| p4 | 9 | Cor.F I.II | DIFF disjoint | {C5,D5} | {Bb4} | medium  scoreUnc |
| p4 | 10 | Cor.F I.II | DIFF partial∩{C5} | {C5,D5} | {Bb4,C5} | medium  scoreUnc |
| p4 | 11 | Cor.F I.II | DIFF disjoint | {C5,D5} | {Bb4} | medium  scoreUnc |
| p4 | 12 | Cor.F I.II | DIFF disjoint | {C5,D5} | {Bb4} | medium  scoreUnc |
| p4 | 13 | Cor.F I.II | DIFF disjoint | {C5,D5} | {A4,Bb4,G4} | medium  scoreUnc |
| p5 | 16 | Cor.F III.IV | DIFF: score=rest, part notes | rest | {F4} | medium  partUnc |
| p5 | 17 | Cor.F III.IV | DIFF disjoint | {A3} | {G4} | low  scoreUnc partUnc |
| p5 | 18 | Cor.F III.IV | DIFF: part=rest, score notes | {A3} | rest | medium  scoreUnc |
| p5 | 19 | Cor.F III.IV | DIFF: score=rest, part notes | rest | {A3,G4} | medium  partUnc |
| p5 | 20 | Cor.F III.IV | DIFF: score=rest, part notes | rest | {G5} | medium  partUnc |
| p6 | 21 | Cor.F III.IV | DIFF: score=rest, part notes | rest | {A4} | medium  partUnc |
| p6 | 22 | Cor.F III.IV | DIFF: score=rest, part notes | rest | {F3} | medium  partUnc |
| p6 | 24 | Cor.F III.IV | DIFF: score=rest, part notes | rest | {A4,C4} | medium  partUnc |
| p6 | 26 | Cor.F III.IV | DIFF: score=rest, part notes | rest | {E4} | medium  partUnc |
| p4 | 7 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p4 | 8 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p4 | 9 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p4 | 10 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p4 | 11 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p4 | 12 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p4 | 13 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p5 | 14 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p5 | 15 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p5 | 16 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p5 | 17 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p5 | 18 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p5 | 19 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p5 | 20 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p6 | 21 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p6 | 22 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p6 | 23 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p6 | 24 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p6 | 25 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p6 | 26 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p6 | 27 | Trbe I.II.F | no-part-read | - | - | info no part decode for trumpet-i,trumpet-ii |
| p4 | 7 | Trbni I.II | agree* (score extra likely missing voice: F3,G3) | {A3,Bb3,F3,G3} | {A3,Bb3} | low no part: trombone-ii |
| p4 | 8 | Trbni I.II | agree* (score extra likely missing voice: Eb3,F3) | {Eb3,F3,G3} | {G3} | low no part: trombone-ii |
| p4 | 9 | Trbni I.II | agree* (score extra likely missing voice: G3) | {C4,G3} | {C4} | low no part: trombone-ii |
| p5 | 14 | Trbni I.II | agree* (score extra likely missing voice: D3,Db3) | {D3,Db3,G3} | {G3} | low no part: trombone-ii scoreUnc |
| p5 | 15 | Trbni I.II | agree* (score extra likely missing voice: G3) | {Bb3,G3} | {Bb3} | low no part: trombone-ii scoreUnc |
| p5 | 16 | Trbni I.II | agree* (score extra likely missing voice: E3,F3,G3) | {A3,B3,C4,E3,F3,G3} | {A3,B3,C4} | low no part: trombone-ii scoreUnc |
| p5 | 17 | Trbni I.II | agree* (score extra likely missing voice: G3) | {B3,G3} | {B3} | low no part: trombone-ii scoreUnc |
| p5 | 18 | Trbni I.II | agree* (score extra likely missing voice: G3) | {B3,G3} | {B3} | low no part: trombone-ii scoreUnc |
| p5 | 17 | Trbni III e Tb | agree* (score extra likely missing voice: B1,D2,F2) | {B1,D2,F1,F2} | {F1} | low no part: trombone-iii scoreUnc |
| p5 | 18 | Trbni III e Tb | agree* (score extra likely missing voice: F2,G1) | {F1,F2,G1} | {F1} | low no part: trombone-iii scoreUnc partUnc |
| p6 | 26 | Trbni III e Tb | DIFF: score=rest, part notes | rest | {D2} | high no part: trombone-iii |
| p6 | 27 | Trbni III e Tb | DIFF: score=rest, part notes | rest | {D2} | high no part: trombone-iii |
