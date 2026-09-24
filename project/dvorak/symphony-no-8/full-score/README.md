# Dvořák 8 — full score (bar numbers only)

Source: the conductor's score *Critical Edition based on the Composer's Manuscript, ed. František Bartoš* (`Bartos.pdf`, 172 PDF pages, supplied through the `source_db8` GitHub release; not committed). SHA-256 `f644a29d78440db51cb15d007be6d0f8198e253f9adb53845e9a8334977f7026`. Printed page = PDF page − 2.

This directory drives the lazy-loaded full-score viewer (`public/score/dvorak8/`) that the reader opens from a bar's context menu. **Only bar positions and numbers are derived; no notes were read.**

| Movement | PDF pages | Bars |
| --- | --- | --- |
| I Allegro con brio | 3–61 | 1–318 |
| II Adagio | 62–94 | 1–170 |
| III Allegretto grazioso | 95–126 | 1–231 (da capo not written out) |
| IV Allegro ma non troppo | 127–172 | 1–389 (first and second endings count as separate bars) |

## Method

1. Render each page at 200 dpi grayscale and deskew it (angle that maximises the vertical projection, ±0.8°).
2. Split the page into systems at the printed `//` system separators (template: the 50×50 glyph crop embedded as `separator` in `score.json`, normalised cross-correlation > 0.6).
3. Barlines are vertical strokes ≥ 150 px (vertical morphological opening). A stroke counts when, after correcting the residual x-shift between staff groups, it covers ≥ 30 % of the system height. Missing start/end lines are taken from the staff-line extent; double and repeat barlines within 28 px are merged.
4. Number bars consecutively per movement, then compare every system's review strip (`--review`) with the printed bar numbers (every 5 bars). All 1108 bars were checked; the 10 pages where detection disagreed are fixed in `score.json` → `overrides`:
   - p41: double barline at *Poco meno mosso* too short to detect (added).
   - p69, p139, p150: courtesy key signature after the final barline (dropped).
   - p129, p135: first/second-ending barlines at the repeats (added).
   - p160–p163: start-repeat sign directly after the clef (dropped).
5. The movement totals equal the Horn II / Trombone I part data (318 / 170 / 231 / 389), so part bar numbers open the matching score bar.

Rebuild: `python3 tools/dynamic/build_score.py --pdf Bartos.pdf --work work --review work/review` (≈2 minutes on 4 cores; needs OpenCV, NumPy, Pillow, and PyMuPDF or Poppler). Validate: `python3 tools/dynamic/validate_score.py`.

## Limits

Barline x positions come from detection and may be a few pixels off. Highlight boxes cover the whole system height. The images are compressed derivatives (1600 px wide, WebP q50) for orientation, not for engraving-level detail.
