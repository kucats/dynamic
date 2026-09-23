# Follow-up 3: bar numbers for every bar (barline segments) of your page

work/bars_auto_pPAGE.json contains, for every system (key = system number counted from the top of the page, 1-based,
by the NEW staff detector — it may differ by one from the numbering you used before, check the overlay),
a list of segments between detected barlines: {"xa": left barline x, "xb": right barline x, "label": auto bar number or ""}.
Run `python3 work/bars_overlay.py PAGE` -> work/barsov_pPAGE_*.png shows each segment start as a red line with "sys.index:label".

Write work/bars_pPAGE.json with the same structure but CORRECT and COMPLETE labels:
- Every segment gets its printed bar number (as a string), e.g. "57".
- A multi-bar rest segment gets a range "61–64" (en dash). A 1st/2nd ending bar gets its number too.
- If a detected "barline" is not a real barline (e.g. a stem), merge the two segments (drop the false one); if a real barline
  was missed, split the segment (add a new xa). Keep xa/xb in page pixels. The very first segment of each system starts at the
  system start; a tiny trailing segment after the final barline must be removed.
- Use your notes' bar numbers (work/final_pPAGE.json) and the printed numbers / multi-rest counts on the page to make
  labels consistent. Movement starts at bar 1.
Then re-run `python3 work/bars_overlay.py PAGE work/bars_pPAGE.json` and look at the images to verify every label.
Reply briefly with how many segments you changed.
