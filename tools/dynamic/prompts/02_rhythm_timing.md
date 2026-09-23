# Follow-up task: add RHYTHM + timing info to your page (for audio playback)

Update your existing file work/final_pPAGE.json IN PLACE. Keep every existing field and note (fix a note only if you find a
real error). Add:

## 1. Per note (every entry in "notes")
- "bar": must now be filled for every note (printed bar number; count carefully with multi-bar rests).
- "dur": written duration as a fraction string of a WHOLE note: "1" whole, "1/2" half, "3/4" dotted half, "1/4" quarter,
  "3/8" dotted quarter, "1/8" eighth, "3/16" dotted eighth, "1/16" sixteenth, "1/32"... Triplets: e.g. eighth in a
  triplet = "1/12", quarter in a triplet = "1/6", sixteenth-triplet = "1/24". Grace notes = "0".
- "off": onset of the note measured from the start of its bar, as a fraction of a whole note (first beat = "0",
  e.g. in 4/4 the 3rd beat = "1/2"; in 3/8 the second eighth = "1/8"). Work it out from the rests and note values
  before it in the bar. Double check that off+dur of the last note never exceeds the bar length.
  (Tied notes: each notehead keeps its own dur/off; tie_from_prev already says it continues.)

## 2. Page-level "meta" object
"meta": {
  "bars": [first_bar_on_page, last_bar_on_page],           // including rest bars; per movement if a movement starts
  "meters":  [{"bar":1,"meter":"4/4"}, ...],                 // every time signature shown on this page (C = 4/4, ¢ = 2/2)
  "tempos":  [{"bar":1,"text":"Allegro con brio","mm":"♩=138"}, ...],   // every tempo word / metronome mark, mm "" if none
  "transpositions": [{"bar":1,"text":"in F"}, ...],          // every "in X" / "muta in X" instruction for the horn and where it takes effect
  "repeats": "free text: repeat barlines, 1st/2nd endings (which bar numbers), D.S./Coda/segno, measure-repeat signs, fermatas on rests; or empty",
  "movement_last_bar": {"I": 355}                           // only if a movement ENDS on your page (final double bar)
}
For bars that belong to different movements on the same page, "bars" may be {"I":[272,318],"II":[1,43]}.

When done, re-run `python3 work/check.py PAGE` (it still works) and also run
`python3 work/check_rhythm.py PAGE` which reports bars whose note durations/offsets look inconsistent with the meter.
Fix what it flags if it is a real error (it cannot see rests, so short bars are fine; overfull bars and overlapping notes are errors).
Reply briefly: meters, tempos, transpositions, repeats found, and any uncertain rhythm spots.
