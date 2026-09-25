# Trombone alternate-position suggestions

`tools/dynamic/trombone_alt.py` suggests alternate slide positions for trombone parts. It trades
slide travel against lip (partial) changes: too much slide movement is hard, and so are too many
partial changes. Suggestions are review material for a player or teacher. They never change the
reader's `pos`, and they are not an audited reading.

## Inputs and outputs

- Input: generated reader data `public/reader/data/<id>.json` (pitch, rhythm, timeline) and the
  option table `tools/dynamic/trombone_positions.json`.
- Output next to each part: `project/**/dynamic/alt-positions.json` (machine-readable) and
  `alt-positions.md` (Japanese review sheet: bar, neighbouring notes, standard → suggested, change in
  slide travel and partial changes, tuning hint).
- `--preset slide|balanced|lip` sets how strongly partial changes are avoided (default `balanced`).
  `--check` fails if the committed outputs are stale.

## Option table

For each pitch (E2–G5, B♭ tenor, no F attachment) the table lists positions on the harmonic series.
- **Standard option:** the reader's position, cost 0.
- **Alternates:** cost ≥ 1. The cost rises for out-of-tune partials (5th and 10th ≈ −14 cents,
  7th ≈ −31 cents), for 6th–7th position and for high partials.
- **Excluded:** the 7th partial in 1st position, high partials (9th+) in 5th–7th position, and the
  13th partial as an alternate.

The table is meant to be edited by a player. The tests check that every option lies on the harmonic
series and that the standard options match `TROMBONE_POS` in `tools/dynamic/common.py`.

## Algorithm

1. Per movement, notes are placed in time from the reader timeline (first pass; D.S. repeats skipped).
2. Each note may take any option from the table. A Viterbi search finds the cheapest sequence:
   - Note cost: the option's cost from the table.
   - Transition cost:
     `urgency × (slide travel in dm + lip_weight × |Δpartial|^1.3 × register factor)`.
     `urgency` is high for fast notes, low for slow notes, and 0.15 after a rest of 0.3 s or more.
     Slow music and rests make every change easy, so standard positions win there.
   - Tied notes keep their option. Unresolved notes (`unc`) break the chain and get no suggestion.
3. Runs of changed notes are grouped into passages. Each passage is bounded by standard notes, so it
   can be kept or dropped on its own. A passage is reported only if it saves at least `MIN_GAIN`
   (0.8) over the standard positions in its surrounding transitions.

## Limits

- No articulation data: slurs, and whether a slide change needs legato tonguing, are not modelled yet.
- Tuning hints come from the partial's deviation. Real instruments and players differ.
- The weights are a first calibration against textbook cases:
  - F3 in 6th between G3s,
  - B♭3 in 5th between B3/C4,
  - D4 in 4th between B3s.

  Adjust them after players review the sheets.

Tests: `python3 -m unittest tests.test_trombone_alt`.
