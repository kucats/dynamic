# Wind/brass cross-check — score staves vs part reads

Dvorak 8, mvt I. Score side: `full-score/score-notes/p005.json`+`p006.json` (branch `devin/decode-score-p5-6`; PDF pp.5-6 = printed pp.3-4), bars 14-27. Part side: `*/dynamic/pages/notes_p*.json` on the `devin/decode-parts-*` branches (trombone-ii via `timing/trombone2-timeline.csv`).

Both sides record **written pitch**, so no transposition is applied (Cl in A / Cor in F / Trbe in F cancel out; Trbni/Cb are concert). Score Trbni I.II staff is alto clef — same convention as the part decode. `unc` = notes the part decode itself flagged uncertain/auto-draft; cue notes already excluded by the part decode are ignored.

**Bars compared: 98 | agreeing: 77 | disagreements: 19 (+ 29 informational rest-vs-flagged-candidate rows)**

Severity: **high** = confident part data contradicts the score read; **medium** = one side flagged uncertain; **low** = adjacent-pitch (±1-2 semitone) mismatch consistent with a positional misread; **info** = not a true conflict (part shows only flagged-uncertain candidates, or the missing voice's part was never decoded).
## Per-bar comparison

| Score staff | Bar | Score says | Part says (confident) | Part uncertain | Verdict |
|---|---|---|---|---|---|
| Fl.I | 14 | score: whole rest | (rest) | {A5,Bb5,C6,D6} | agree (rest; part has flagged-uncertain reads {A5,Bb5,C6,D6}) |
| Fl.I | 15 | rest | (rest) | {C6,D6,Eb6,F6} | agree (rest; part has flagged-uncertain reads {C6,D6,Eb6,F6}) |
| Fl.I | 16 | rest | (rest) | {G5,A5,Bb5,C6,D6,Eb6} | agree (rest; part has flagged-uncertain reads {G5,A5,Bb5,C6,D6,Eb6}) |
| Fl.I | 17 | rest | (rest) | {C6,D6,Eb6,F6} | agree (rest; part has flagged-uncertain reads {C6,D6,Eb6,F6}) |
| Fl.I | 18 | [G5 half][B5 half] | {G5,B5} | {Bb5,C6,D6,Eb6,F6,G6} | agree (part extra unc reads {Bb5,C6,D6,Eb6,F6,G6}) |
| Fl.I | 19 | call: 16th-rest + B5 16th + triad 8th x4; triad members uncertain {G5,B5,D6} vs {A5,C6,E6} | {B5,D6,E6} | {A5,Bb5,C6,G6,A6} | agree-subset (score subset of part; score read was unc) |
| Fl.I | 20 | [q rest][B5 q][rests]; rhythm uncertain | (rest) | {F#5,G5,A5,Bb5,B5,D6,Eb6,F6,G6} | weak-agree (score pitches all present in part's uncertain reads): score {B5} vs part-uncertain {F#5,G5,A5,Bb5,B5,D6,Eb6,F6,G6} |
| Fl.I | 21 | bird call ~5-6 notes descending ~D6/C6 -> E5/C5 zone, per-note +-1-2 | {D6} | {G5,A5,Bb5,C6,D6,Eb6} | DISAGREE: score {C5,E5,C6,D6} vs part {D6} |
| Fl.I | 22 | rest | (rest) | {G5,A5,Bb5,C6,D6,Eb6} | agree (rest; part has flagged-uncertain reads {G5,A5,Bb5,C6,D6,Eb6}) |
| Fl.I | 23 | rest | (rest) | {A5,Bb5,D6,Eb6,F6,F#6,G6,A6} | agree (rest; part has flagged-uncertain reads {A5,Bb5,D6,Eb6,F6,F#6,G6,A6}) |
| Fl.I | 24 | rest | (rest) | {C6,C#6,D6,Eb6,F6,F#6,G6} | agree (rest; part has flagged-uncertain reads {C6,C#6,D6,Eb6,F6,F#6,G6}) |
| Fl.I | 25 | rest | (rest) | {A5,Bb5,C6,D6,Eb6,A6,Bb6} | agree (rest; part has flagged-uncertain reads {A5,Bb5,C6,D6,Eb6,A6,Bb6}) |
| Fl.I | 26 | rest | (rest) | {Eb5,F5,G5,A5,D6,G6,G#6} | agree (rest; part has flagged-uncertain reads {Eb5,F5,G5,A5,D6,G6,G#6}) |
| Fl.I | 27 | rest | (rest) | {G6,A6,C#7} | agree (rest; part has flagged-uncertain reads {G6,A6,C#7}) |
| Fl.II/Fl.picc | 14 | rest | (rest) | {D4,G4,B4,G5,B5} | agree (rest; part has flagged-uncertain reads {D4,G4,B4,G5,B5}) |
| Fl.II/Fl.picc | 15 | rest | (rest) | {D4,G4,B4,D5,G5} | agree (rest; part has flagged-uncertain reads {D4,G4,B4,D5,G5}) |
| Fl.II/Fl.picc | 16 | rest | (rest) | {D4,G4,B4,D5,G5,B5} | agree (rest; part has flagged-uncertain reads {D4,G4,B4,D5,G5,B5}) |
| Fl.II/Fl.picc | 17 | rest | (rest) | {C4,Eb4,G4,B5,C6,D6} | agree (rest; part has flagged-uncertain reads {C4,Eb4,G4,B5,C6,D6}) |
| Fl.II/Fl.picc | 18 | rest | (rest) | {A4,B4,C5,D5,Eb5,G5,A5,B5} | agree (rest; part has flagged-uncertain reads {A4,B4,C5,D5,Eb5,G5,A5,B5}) |
| Fl.II/Fl.picc | 19 | rest | (rest) | {D4,F#4,A4,D5,E5,F#5,G5,A5} | agree (rest; part has flagged-uncertain reads {D4,F#4,A4,D5,E5,F#5,G5,A5}) |
| Fl.II/Fl.picc | 20 | rest | (rest) | {G4,B4,C5,D5} | agree (rest; part has flagged-uncertain reads {G4,B4,C5,D5}) |
| Fl.II/Fl.picc | 21 | 'muta in Fl. picc.' marked; no notes | (rest) | {C5,D5,Eb5,G5,B5} | agree (rest; part has flagged-uncertain reads {C5,D5,Eb5,G5,B5}) |
| Fl.II/Fl.picc | 22 | ~D5 whole pedal tied across, p; D5 vs E5 uncertain | (rest) | {B4,D5,Eb5,G5,A5} | weak-agree (score pitches all present in part's uncertain reads): score {D5} vs part-uncertain {B4,D5,Eb5,G5,A5} |
| Fl.II/Fl.picc | 23 | ~D5 whole pedal tied across, p; D5 vs E5 uncertain | (rest) | {D5,Eb5,F#5,G5,A5,C#6} | weak-agree (score pitches all present in part's uncertain reads): score {D5} vs part-uncertain {D5,Eb5,F#5,G5,A5,C#6} |
| Fl.II/Fl.picc | 24 | ~D5 whole pedal tied across, p; D5 vs E5 uncertain | (rest) | {D5,G5,B5,C6} | weak-agree (score pitches all present in part's uncertain reads): score {D5} vs part-uncertain {D5,G5,B5,C6} |
| Fl.II/Fl.picc | 25 | ~D5 whole pedal tied across, p; D5 vs E5 uncertain | (rest) | {G5,A5,B5,C6,D6} | DISAGREE?: score {D5} vs part-uncertain {G5,A5,B5,C6,D6} |
| Fl.II/Fl.picc | 26 | ~D5 whole pedal tied across, p; D5 vs E5 uncertain | (rest) | {G5,A5,B5,C6,D6} | DISAGREE?: score {D5} vs part-uncertain {G5,A5,B5,C6,D6} |
| Fl.II/Fl.picc | 27 | ~D5 whole pedal tied across, p; D5 vs E5 uncertain | (rest) | {F5,G5,A5,B5,C6,D6,Eb6} | DISAGREE?: score {D5} vs part-uncertain {F5,G5,A5,B5,C6,D6,Eb6} |
| Cl.I.II (in A) | 14 | Eb4 half x2 | {D4} | {G4,G5} | DISAGREE: score {Eb4} vs part {D4} |
| Cl.I.II (in A) | 15 | Eb4 whole | {F4} | {F4,G4} | DISAGREE: score {Eb4} vs part {F4} |
| Cl.I.II (in A) | 16 | Eb4 whole | (rest) | {E4,F4} | DISAGREE?: score {Eb4} vs part-uncertain {E4,F4} |
| Cl.I.II (in A) | 17 | Eb4 whole | (rest) | {D4,F4} | DISAGREE?: score {Eb4} vs part-uncertain {D4,F4} |
| Cl.I.II (in A) | 18 | Eb4 q + rests | (rest) | {} | DISAGREE: score notes, part silent |
| Cl.I.II (in A) | 19 | implied rest | (rest) | {} | agree (rest) |
| Cl.I.II (in A) | 20 | implied rest | (rest) | {F4} | agree (rest; part has flagged-uncertain reads {F4}) |
| Cl.I.II (in A) | 21 | rest | (rest) | {} | agree (rest) |
| Cl.I.II (in A) | 22 | rest | (rest) | {} | agree (rest) |
| Cl.I.II (in A) | 23 | rest | (rest) | {} | agree (rest) |
| Cl.I.II (in A) | 24 | rest | (rest) | {} | agree (rest) |
| Cl.I.II (in A) | 25 | rest | (rest) | {C4} | agree (rest; part has flagged-uncertain reads {C4}) |
| Cl.I.II (in A) | 26 | rest | (rest) | {} | agree (rest) |
| Cl.I.II (in A) | 27 | rest | (rest) | {} | agree (rest) |
| Cor I.II (in F) | 14 | F4 half, G4 half (a 2) | {F4,G4} | {} | agree |
| Cor I.II (in F) | 15 | A4 whole | {A4} | {} | agree |
| Cor I.II (in F) | 16 | A4 whole | {A4} | {} | agree |
| Cor I.II (in F) | 17 | A4 whole | {A4} | {} | agree |
| Cor I.II (in F) | 18 | A4 q + rests | {A4} | {} | agree |
| Cor I.II (in F) | 19 | rest | (rest) | {} | agree (rest) |
| Cor I.II (in F) | 20 | rest | (rest) | {} | agree (rest) |
| Cor I.II (in F) | 21 | rest | (rest) | {} | agree (rest) |
| Cor I.II (in F) | 22 | rest | (rest) | {} | agree (rest) |
| Cor I.II (in F) | 23 | rest | (rest) | {} | agree (rest) |
| Cor I.II (in F) | 24 | rest | (rest) | {} | agree (rest) |
| Cor I.II (in F) | 25 | rest | (rest) | {} | agree (rest) |
| Cor I.II (in F) | 26 | rest | (rest) | {} | agree (rest) |
| Cor I.II (in F) | 27 | rest | (rest) | {} | agree (rest) |
| Cor III.IV (in F) | 14 | rest | (rest) | {} | agree (rest) |
| Cor III.IV (in F) | 15 | rest | (rest) | {} | agree (rest) |
| Cor III.IV (in F) | 16 | rest | (rest) | {F4} | agree (rest; part has flagged-uncertain reads {F4}) |
| Cor III.IV (in F) | 17 | low voice A3 whole; upper voice rest | (rest) | {G4} | DISAGREE?: score {A3} vs part-uncertain {G4} |
| Cor III.IV (in F) | 18 | A3 q + rests | (rest) | {} | DISAGREE: score notes, part silent |
| Cor III.IV (in F) | 19 | rest | (rest) | {A3,G4} | agree (rest; part has flagged-uncertain reads {A3,G4}) |
| Cor III.IV (in F) | 20 | rest | (rest) | {G5} | agree (rest; part has flagged-uncertain reads {G5}) |
| Cor III.IV (in F) | 21 | rest | (rest) | {A4} | agree (rest; part has flagged-uncertain reads {A4}) |
| Cor III.IV (in F) | 22 | rest | (rest) | {F3} | agree (rest; part has flagged-uncertain reads {F3}) |
| Cor III.IV (in F) | 23 | rest | (rest) | {} | agree (rest) |
| Cor III.IV (in F) | 24 | rest | (rest) | {C4,A4} | agree (rest; part has flagged-uncertain reads {C4,A4}) |
| Cor III.IV (in F) | 25 | rest | (rest) | {} | agree (rest) |
| Cor III.IV (in F) | 26 | rest | (rest) | {E4} | agree (rest; part has flagged-uncertain reads {E4}) |
| Cor III.IV (in F) | 27 | rest | (rest) | {} | agree (rest) |
| Trbni I.II (alto staff) | 14 | {G3+D3} half, {G3+Db3-ish} half; lower voice uncertain | {D3,Eb3,G3} | {} | DISAGREE: score {Db3,D3,G3,G3} vs part {D3,Eb3,G3} |
| Trbni I.II (alto staff) | 15 | {Bb3+G3} whole | {G3,Bb3} | {} | agree |
| Trbni I.II (alto staff) | 16 | upper A3 h,B3 q,C4 q; lower ~F3/G3 h -> E3-ish q | {F#3,G3,A3,B3,C4} | {} | DISAGREE: score {E3,F3,G3,A3,B3,C4} vs part {F#3,G3,A3,B3,C4} |
| Trbni I.II (alto staff) | 17 | {B3+G3} whole tied | {G3,B3} | {} | agree |
| Trbni I.II (alto staff) | 18 | {B3+G3} q + rests | {G3,B3} | {} | agree |
| Trbni I.II (alto staff) | 19 | rest | (rest) | {} | agree (rest) |
| Trbni I.II (alto staff) | 20 | rest | (rest) | {} | agree (rest) |
| Trbni I.II (alto staff) | 21 | rest | (rest) | {} | agree (rest) |
| Trbni I.II (alto staff) | 22 | rest | (rest) | {} | agree (rest) |
| Trbni I.II (alto staff) | 23 | rest | (rest) | {} | agree (rest) |
| Trbni I.II (alto staff) | 24 | rest | (rest) | {} | agree (rest) |
| Trbni I.II (alto staff) | 25 | rest | (rest) | {} | agree (rest) |
| Trbni I.II (alto staff) | 26 | rest | (rest) | {} | agree (rest) |
| Trbni I.II (alto staff) | 27 | rest | (rest) | {} | agree (rest) |
| Trbni III e Tb | 14 | rest | (rest) | {} | agree (rest) |
| Trbni III e Tb | 15 | rest | (rest) | {} | agree (rest) |
| Trbni III e Tb | 16 | rest | (rest) | {} | agree (rest) |
| Trbni III e Tb | 17 | {F2 + F1-ish} whole dyad; low voice F1 vs G1/E1 uncertain | {F1} | {} | agree-partial: part {F1} ⊆ score; unmatched score pitches belong to trombone-iii (no decode) |
| Trbni III e Tb | 18 | {F2 + F1/G1-ish} filled q + rests | (rest) | {F1} | agree-partial: part-unc ⊆ score; unmatched score pitches may belong to trombone-iii (no decode): score {F1,F2} vs part-uncertain {F1} |
| Trbni III e Tb | 19 | rest | (rest) | {} | agree (rest) |
| Trbni III e Tb | 20 | rest | (rest) | {} | agree (rest) |
| Trbni III e Tb | 21 | rest | (rest) | {} | agree (rest) |
| Trbni III e Tb | 22 | rest | (rest) | {} | agree (rest) |
| Trbni III e Tb | 23 | rest | (rest) | {} | agree (rest) |
| Trbni III e Tb | 24 | rest | (rest) | {} | agree (rest) |
| Trbni III e Tb | 25 | rest | (rest) | {} | agree (rest) |
| Trbni III e Tb | 26 | rest | {D2} | {} | DISAGREE: score rest, part plays {D2} |
| Trbni III e Tb | 27 | rest | {D2} | {} | DISAGREE: score rest, part plays {D2} |

## Disagreements

| Bar | Staff | Score says | Part says | Severity | Notes |
|---|---|---|---|---|---|
| 20 | Fl.I | {B5} | {F#5,G5,A5,Bb5,B5,D6,Eb6,F6,G6} (all uncertain) | **low** | part has only uncertain reads |
| 21 | Fl.I | {C5,E5,C6,D6} | {D6} | **medium** | missing from part: {C5,E5,C6}; extra in part: -; part also unc {G5,A5,Bb5,C6,D6,Eb6} — score read is a coarse 'descending D6/C6 -> E5/C5' gesture; part confident D6 half + flagged run notes — real pitches of the call need a zoomed re-read |
| 22 | Fl.II/Fl.picc | {D5} | {B4,D5,Eb5,G5,A5} (all uncertain) | **low** | part has only uncertain reads |
| 23 | Fl.II/Fl.picc | {D5} | {D5,Eb5,F#5,G5,A5,C#6} (all uncertain) | **low** | part has only uncertain reads |
| 24 | Fl.II/Fl.picc | {D5} | {D5,G5,B5,C6} (all uncertain) | **low** | part has only uncertain reads |
| 25 | Fl.II/Fl.picc | {D5} | {G5,A5,B5,C6,D6} (all uncertain) | **medium** | part has only uncertain reads |
| 26 | Fl.II/Fl.picc | {D5} | {G5,A5,B5,C6,D6} (all uncertain) | **medium** | part has only uncertain reads |
| 27 | Fl.II/Fl.picc | {D5} | {F5,G5,A5,B5,C6,D6,Eb6} (all uncertain) | **medium** | part has only uncertain reads |
| 14 | Cl.I.II (in A) | {Eb4} | {D4} | **low** | missing from part: {Eb4}; extra in part: {D4}; part also unc {G4,G5} |
| 15 | Cl.I.II (in A) | {Eb4} | {F4} | **low** | missing from part: {Eb4}; extra in part: {F4}; part also unc {F4,G4} |
| 16 | Cl.I.II (in A) | {Eb4} | {E4,F4} (all uncertain) | **medium** | part has only uncertain reads |
| 17 | Cl.I.II (in A) | {Eb4} | {D4,F4} (all uncertain) | **medium** | part has only uncertain reads |
| 18 | Cl.I.II (in A) | {Eb4} | (rest) | **medium** | score read notes; part has nothing in bar — cl-i's last confident note is F4 q @off3/4 of b17 with an unresolved rest-glyph boundary — the score's b18 Eb4 q may be the same note read a step up / a bar late; cl-ii auto-decode is unreliable |
| 17 | Cor III.IV (in F) | {A3} | {G4} (all uncertain) | **medium** | part has only uncertain reads — score low voice A3 (uncertain) vs horn-iv auto-draft G4 — 2 semitones, both low-confidence; needs human zoom |
| 18 | Cor III.IV (in F) | {A3} | (rest) | **medium** | score read notes; part has nothing in bar — possible off-by-one of the b17 note on either side |
| 14 | Trbni I.II (alto staff) | {Db3,D3,G3,G3} | {D3,Eb3,G3} | **low** | missing from part: {Db3}; extra in part: {Eb3} — score 'Db3-ish' vs tb2 Eb3 — score itself marked the read uncertain |
| 16 | Trbni I.II (alto staff) | {E3,F3,G3,A3,B3,C4} | {F#3,G3,A3,B3,C4} | **low** | missing from part: {E3,F3}; extra in part: {F#3} — score lower-voice '~F3/G3 -> E3-ish' vs tb2's G3,F#3 8ths — within +-2 semitones, both flagged uncertain |
| 26 | Trbni III e Tb | score=rest | {D2} | **high** | score claims whole-bar rest; part has confident notes — tuba part: D2 whole at b26-33, bar numbers verified against printed numerals; coincides with the score's Timp D3 roll at b26-27 — score likely missed the tuba pedal |
| 27 | Trbni III e Tb | score=rest | {D2} | **high** | score claims whole-bar rest; part has confident notes — same tuba D2 pedal as b26 |

## Informational rows (not conflicts)

| Bar | Staff | Score says | Part says | Notes |
|---|---|---|---|---|
| 14 | Fl.I | rest | {A5,Bb5,C6,D6} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 15 | Fl.I | rest | {C6,D6,Eb6,F6} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 16 | Fl.I | rest | {G5,A5,Bb5,C6,D6,Eb6} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 17 | Fl.I | rest | {C6,D6,Eb6,F6} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 22 | Fl.I | rest | {G5,A5,Bb5,C6,D6,Eb6} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 23 | Fl.I | rest | {A5,Bb5,D6,Eb6,F6,F#6,G6,A6} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 24 | Fl.I | rest | {C6,C#6,D6,Eb6,F6,F#6,G6} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 25 | Fl.I | rest | {A5,Bb5,C6,D6,Eb6,A6,Bb6} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 26 | Fl.I | rest | {Eb5,F5,G5,A5,D6,G6,G#6} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 27 | Fl.I | rest | {G6,A6,C#7} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 14 | Fl.II/Fl.picc | rest | {D4,G4,B4,G5,B5} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 15 | Fl.II/Fl.picc | rest | {D4,G4,B4,D5,G5} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 16 | Fl.II/Fl.picc | rest | {D4,G4,B4,D5,G5,B5} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 17 | Fl.II/Fl.picc | rest | {C4,Eb4,G4,B5,C6,D6} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 18 | Fl.II/Fl.picc | rest | {A4,B4,C5,D5,Eb5,G5,A5,B5} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 19 | Fl.II/Fl.picc | rest | {D4,F#4,A4,D5,E5,F#5,G5,A5} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 20 | Fl.II/Fl.picc | rest | {G4,B4,C5,D5} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 21 | Fl.II/Fl.picc | rest | {C5,D5,Eb5,G5,B5} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 20 | Cl.I.II (in A) | rest | {F4} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 25 | Cl.I.II (in A) | rest | {C4} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 16 | Cor III.IV (in F) | rest | {F4} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 19 | Cor III.IV (in F) | rest | {A3,G4} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 20 | Cor III.IV (in F) | rest | {G5} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 21 | Cor III.IV (in F) | rest | {A4} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 22 | Cor III.IV (in F) | rest | {F3} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 24 | Cor III.IV (in F) | rest | {C4,A4} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 26 | Cor III.IV (in F) | rest | {E4} (all uncertain) | score claims rest; part decode has only flagged-uncertain candidate reads |
| 17 | Trbni III e Tb | {F1,F2} | {F1} | missing from part: {F2}; extra in part: -; NOTE: trombone-iii has no bar-aligned part decode — its voice is unverifiable, missing pitches may belong to it |
| 18 | Trbni III e Tb | {F1,F2} | {F1} (all uncertain) | part has only uncertain reads; NOTE: trombone-iii not bar-aligned |

## Not comparable / gaps

- **Ob.I.II, Fag.I.II, Trbe I.II**: no decoded part branches exist (only bass/cello/clarinet/flute/horn/trombone/viola/violin2 were decoded), so the score's all-rest claims for these staves in bars 14-27 are unverified.
- **Trbni III** (upper voice, staff 10): the trombone-iii branch carries mvt I only as unreviewed raw OMR (`publication-source/legacy-catalog`) with no bar alignment; its first confirmed notes (p10 sys2: D3,G3,E3,B3...) cannot be mapped to bars 17-18 without a bar index.
- **Timpani** is out of the wind/brass scope; note the score's Timp D3 roll at b26-27 coincides with the tuba D2 claim below.

Generated by `work/xcheck_wind.py`.