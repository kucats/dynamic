# Task: transcribe ONE page of the cello part (Verdi, Nabucco — VIOLONCELLO, whole opera) — pitch, rhythm, bars

Working dir: the repository root. Your page image: work/pPAGE.png (300 dpi grayscale, ~2967x3904 px;
PAGE = physical PDF page number 1-62).

The instrument is Violoncello — **non-transposing**: the written pitch IS concert pitch (C4 = middle C).

Tools (run with `~/venvs/dynamic/bin/python`):
- `python3 tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png (left/right halves of system SYS,
  1-based from top). `python3 tools/dynamic/zoom.py PAGE SYS X0 X1 OUT.png` -> custom x range (~500–800 px
  close-ups; use these whenever a chord stack, a dense run, or a ledger-line area is ambiguous).
  Pitch guides on the left margin: treble names (red/green), (bass) in grey, [alto] in purple,
  <tenor> in cyan/orange — each tick is exactly at that line/space height; the same row shows what a
  notehead AT THAT HEIGHT reads in each clef. A blue x-ruler in PAGE pixel coordinates is at the top.
  Candidate noteheads from work/cand_pPAGE.json are circled with ids — weak hints only (this engraving is
  poorly detected: hollow heads, beamed groups, ledger lines and tenor-clef notes are often missed, and
  dynamics/rests/clefs are sometimes circled). Find every notehead yourself.
- `python3 tools/dynamic/check.py PAGE` draws your notes on the page (work/chk_pPAGE_*.png) — always inspect
  it before finishing.
- `python3 tools/dynamic/check_rhythm.py PAGE` checks durations/offsets against the meter.
- `python3 tools/dynamic/make_bars_auto.py PAGE` drafts work/bars_auto_pPAGE.json (barline detection + label
  guess); `python3 tools/dynamic/bars_overlay.py PAGE [work/bars_pPAGE.json]` draws the segments for checking.

## Clefs (cello specifics — IMPORTANT)
- Mostly **bass clef** (F clef on the 4th line; bottom line = G2). Use the grey (bass) guides.
- **Tenor clef** (C clef centred on the 4th line = C4) appears in high passages: lines bottom-up are
  D3 F3 A3 C4 E4. Use the cyan <tenor> guides.
- **Treble clef** for the highest passages: red/green guides.
- Clefs can change mid-system — look for a small clef printed before a barline or between phrases.
  Record clef per note as "bass" | "tenor" | "treble".

## Reading rules (important)
- **Key signatures ARE printed** in this part (e.g. 4 sharps in the Sinfonia) — read the clef area of EVERY
  system; the signature can change at number headings or mid-page. Record each printed signature in
  meta.key_signatures with the page-local bar where it takes effect.
- An accidental lasts until the end of the bar on the same staff position, carries over a tie into the next
  bar, and is cancelled by a natural. Be extremely careful with every ♭, ♯ and ♮ (dropped accidentals were a
  specific complaint).
- Use scientific octaves (C4 = middle C; bass bottom line = G2, tenor bottom line = D3, treble bottom
  line = E4).
- **Chords/double-stops**: 19th-century cello parts stack 2-4 noteheads (divisi or true chords). Include every
  notehead of the stack at its own y. When a chord's voicing is genuinely unreadable, include your best
  reading and set uncertain, e.g. "chord top E3 or G3".
- **Cue notes** (small noteheads of another instrument, usually under a label like "Vl.i", "Ob.", "Fg.",
  "Corni" or sung text, often alongside a rest in the same bar): include them with "sim": true AND
  "uncertain": "cue:<label>" so they are excluded from playback. If unsure whether a note is a cue, include
  it with sim:true + uncertain "maybe cue".
- **Measure-repeat signs** (a slash with two dots, or "%"): output the notes of the repeated bar again with
  "sim": true, same pitch/dur/off, y = the staff's middle line, x spread evenly inside that bar in onset order.
- **Tremolo / repeated-note shorthand** (strokes through the stem): record the written note with its notated
  duration and set "uncertain": "tremolo" (do not expand into repetitions).
- **Multi-bar rests** (a printed number over a thick diagonal/rectangular rest): the rest counts its FULL
  length in bars — a printed "8" rest is 8 bars. Emit no notes for them; the bars pass labels them "a–b".
- Dynamics, fingerings (small digits like 0-4 over notes), bowings and slurs are not recorded — but record
  rehearsal marks (boxed numbers/letters) and section headings.
- Handwritten pencilled annotations: exclude, mention in issues.

## Pass 1 — pitch -> work/final_pPAGE.json
{"page":PAGE,
 "movements":[{"mvt":"<printed heading>","starts_at":{"sys":S,"x":X,"local_bar":B}}],
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"F#3","clef":"bass","bar":5,
           "dur":"1/4","off":"0","tie_from_prev":false,"sim":false,"uncertain":""}, ...],
 "meta":{...}}
- One entry per played notehead in reading order (system by system, left to right); x,y = notehead centre in
  PAGE pixels (±10 px).
- "bar": PAGE-LOCAL bar number — the first bar on the page is 1, counting continues across any movement
  boundary without resetting; a printed "8" multi-rest counts as 8 bars.
- movements[]: every NEW section/number heading printed on this page ("SINFONIA", "ATTO 1.o / Nº 1. Coro
  d'Introduzione", "RECITATIVO", "CAVATINA", "CORO", "Gran Scena", "TACET" …). starts_at.local_bar = the
  page-local bar where the new number's music starts. Continued numbers need no entry.
- If your page **begins mid-bar** (the previous page's bar continues, e.g. a tie in), that first segment is
  local bar **0** — not counted in local_bar_count — and meta.continues_from_prev=true. If your page **ends
  mid-bar**, meta.continues_to_next=true.
Then run check.py and fix misplaced/missing/extra notes and wrong pitches.

## Pass 2 — rhythm + timing (update work/final_pPAGE.json in place)
Keep every field; add per note:
- "dur": fraction of a WHOLE note: "1", "1/2", "3/4", "1/4", "3/8", "1/8", "3/16", "1/16", "1/32"; triplet
  eighth "1/12", triplet quarter "1/6"; grace "0".
- "off": onset from the start of its bar in whole-note fractions (beat 1 = "0"; 4/4 beat 3 = "1/2"). Compute
  from the rests/values before it. off+dur must never exceed the bar length.
Fill "meta" fully:
{"bars":[first_local,last_local],
 "meters":[{"bar":N,"meter":"4/4"}],          // every time signature in force; include the one in force at
                                             // the page top even if not reprinted (C = 4/4, ¢ = 2/2)
 "tempos":[{"bar":N,"text":"Andante","mm":""}],   // tempo words + metronome marks ("" if none)
 "key_signatures":[{"bar":N,"key":"4 sharps"}],   // every printed signature, incl. the one in force at top
 "rehearsal":[{"bar":N,"mark":"3"}],              // boxed rehearsal numbers/letters
 "repeats":"free text (repeat barlines, 1st/2nd endings, segno/coda, D.S./D.C., fermatas; or '')",
 "local_bar_count":N, "continues_from_prev":false, "continues_to_next":false,
 "movement_last_bar":{"<mvt>":<local bar>},       // only if a number ENDS on this page
 "clef_changes":"free text", "cues_excluded":"free text"}
Then re-run check.py and check_rhythm.py; fix overfull bars and overlapping notes it reports (short bars are
fine — rests are not notes).

## Pass 3 — bar numbers -> work/bars_pPAGE.json
work/bars_auto_pPAGE.json holds {"SYS":[{"xa":left,"xb":right,"label":"N or ''"},...]} between detected
barlines (same system numbering as cand_pPAGE.json). Run bars_overlay.py PAGE first to see the draft.
Write work/bars_pPAGE.json with the same structure but CORRECT and COMPLETE PAGE-LOCAL labels:
- every segment gets its page-local bar number as a string;
- a multi-bar rest segment gets a range "61–64" (en dash);
- a page-start continuation segment gets "0";
- drop false barlines (stems are often detected as barlines — common in dense beamed passages), split
  segments where a real barline was missed, remove the tiny tail after a system's final barline; the first
  segment starts at the system start;
- labels must strictly increase along each system and continue across systems (last label of system S <
  first label of system S+1);
- keep xa/xb in PAGE pixels.
Every note must fall inside the segment carrying its bar number. Verify with bars_overlay.py and
check_rhythm.py.

## Report
Note count, bar range, movement headings found, clef changes, key signatures, meters/tempos, repeats,
continues flags, uncertain items.
Do not edit any files outside work/. NEVER commit the PDF or any .png.
