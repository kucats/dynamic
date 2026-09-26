# Rhythm-structure validation of decoded parts — 2026-09-26

Mechanical narrowing of the ~3,700 `auto-draft` (LLM-decoded, unaudited) notes.
Structural consistency check only — NOT a note-level audit (per AGENTS.md,
flagged status stands until source review).

Method: per (movement, bar), take the UNION of note [off, off+dur) spans
(chords/divisi at the same offset share duration — earlier naive sum produced
false overfull flags for every divisi bar). Dur parsing: fraction of whole
note; bare integers are denominators ('8' = eighth); '.' suffix = dotted;
named tokens w/h/q/t8/t16. Flag when union > meter length × 9/8, with meter
from part.json movement meters and movement routing via filename page number
(`d.page` is the source-PDF page, not the logical page — same bug class fixed
in export_follow_ref.py).

## Result

| scope | bars checked | overfull |
|---|---|---|
| dvorak8 all 21 parts | ~8,300 | **1** |
| nabucco 8 parts landed | ~3,800 | 0 |

Single flag:

- **violin-i, mvt III, bar 38**: spans sum to 7/4 against 3/2 meter — last
  note `D6 dur="1"` (whole) at off 3/4. Duration should likely be `3/4`
  (dotted half). Left as review item; not silently corrected.

Everything else, including all the previously mass-flagged auto-draft
regions (horn-i/iii/iv, tuba), is rhythmically consistent: onsets and
durations partition their bars correctly. This raises confidence in the bulk
decode but says nothing about individual pitch correctness — pitch errors
remain covered by the score cross-check layer (crosscheck branches) and the
unc/sim flags.

Script: work/eval/overfull_check (one-off, reproduced inline in workflow
ops notes); output work/eval/overfull_report.json.
