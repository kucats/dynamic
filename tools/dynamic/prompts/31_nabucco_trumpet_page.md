# Task: transcribe ONE page of a trumpet part (Verdi, Nabucco — Tromba I, whole opera) — pitch, rhythm, bars

Working dir: the repository root. Your page image: work/pPAGE.png (300 dpi grayscale, ~2970x3900 px).
The PDF is a 36-page scan of the complete Tromba I part: Sinfonia + the whole opera (acts I–IV, each
split into "numbers" — Coro, Cavatina, Duetto, Finale … — each number is a movement that restarts its bar
count at 1; numbers may start mid-page between systems).

Tools (always run with `~/venvs/dynamic/bin/python` from the repo root):
- `~/venvs/dynamic/bin/python tools/dynamic/zoom.py PAGE SYS` -> work/z_pPAGE_sSYS_a.png / _b.png (left/right
  halves of system SYS, 1-based from top). `... zoom.py PAGE SYS X0 X1 OUT.png` -> custom x range (~500–800 px).
  Left margin pitch guides: treble names (red/green), (bass) grey, [alto] purple — each tick is exactly that
  line/space height. Blue x-ruler on top = PAGE pixel coordinates. Candidate noteheads from work/cand_pPAGE.json
  are circled — they are only weak hints (this engraving detects almost nothing); find every notehead yourself.
- `~/venvs/dynamic/bin/python tools/dynamic/check.py PAGE` draws your notes on the page (work/chk_pPAGE_*.png).
- `~/venvs/dynamic/bin/python tools/dynamic/check_rhythm.py PAGE` checks durations/offsets against the meter.
- `~/venvs/dynamic/bin/python tools/dynamic/bars_overlay.py PAGE [work/bars_pPAGE.json]` draws bar segments.

## Reading rules (important)
- Everything is **treble clef** (report `"clef":"G"`). This is a **transposing trumpet**: crook marks change
  per number — `"in Re"` = D, `"in Mi"` = E, `"in Do"` = C, `"in Mib"` = Eb (also possibly Sol=G, Fa=F,
  Sib=Bb). `pitch` = the WRITTEN pitch as printed (scientific notation, C4 = middle C). Put the current crook
  on EVERY note as `"horn_key":"D"|"E"|"C"|"Eb"` (letter only) and every change in meta.transpositions.
- **No printed bar numbers** → number bars PAGE-LOCALLY: the first bar on the page is 1, multi-bar rests count
  their full length (a "15" block = 15 bars), % repeat bars and "Vuota" (empty) bars each count as one bar.
  Keep counting continuously across a mid-page movement change — your meta.segments list disambiguates.
- **Cue notes are the main trap**: passages printed under sung text (lyrics, "col canto", "Coro", voice
  names) or labelled with another instrument ("Tr.ne I.", "Ob.", "Clar.", "Timp.") are cues — EXCLUDE them.
  In this edition cue heads are often NORMAL size; judge by lyric text / instrument label / a whole rest in
  the same bar. When genuinely unsure, include the note with `uncertain:"could be cue"`.
- **Measure-repeat signs** (% or slash with two dots, often numbered 2 3 4… above): for every such bar output
  the notes of the repeated bar again with `"sim":true`, same pitch/dur/off, `y` = staff middle line, `x`
  spread evenly inside that bar.
- Accidentals persist within a bar and carry over ties; ♮ cancels. Check for a **key signature** at every
  system start, double barline, and movement start (this edition sometimes prints one) — record it in
  meta.key_signatures and apply it to every octave. Many old trumpet parts have none: then only printed
  accidentals apply.
- Record **meters** (C = 4/4, ¢ = 2/2; also 3/4, 3/8, 6/8) — include the meter in force at the page top even
  if not reprinted — **tempos** (words/metronome marks), **rehearsal marks** (boxed numbers like 15, or
  letters A B C… in the Sinfonia) into meta.rehearsal, I./II. Volta endings / ‖: :‖ / D.S. / segno / fermatas
  into meta.repeats, and centered movement headers into "movements" (with {"title","starts_at":{"sys","x"}}).
  An inline "Recit."/"Andante" over a staff is a tempo/character marking inside the same number, NOT a new
  movement; a centered capitals header is a new movement. A "(Tace)" note means the next number is silent —
  record it in issues, transcribe nothing for it.

## Output: work/final_pPAGE.json
{"page":PAGE,
 "movements":[{"title":"Coro di Leviti","key":"A2-leviti","starts_at":{"sys":S,"x":X}}],   // starts ON this page only
 "notes":[{"sys":1,"x":1234,"y":567,"pitch":"C5","clef":"G","bar":3,"dur":"1/4","off":"1/2",
           "tie_from_prev":false,"sim":false,"horn_key":"D","uncertain":"","page_local_bar":3}, ...],
 "meta":{"bars":[1,N],
         "segments":[{"key":"A2-leviti","local_first":1,"local_last":9},
                      {"key":"A2-finale","local_first":10,"local_last":22}],   // every page-local bar covered exactly once
         "meters":[{"bar":1,"meter":"4/4"}], "tempos":[{"bar":1,"text":"Allegro","mm":""}],
         "transpositions":[{"bar":1,"text":"in Re","key":"D"}],
         "key_signatures":[{"bar":1,"key":"none"}],
         "rehearsal":[{"mark":"27","bar":12}],
         "repeats":"free text: repeat barlines, I./II. Volta, D.S./segno/coda, fermatas, % chains, multi-rests list",
         "local_bar_count": N,
         "movement_last_bar": {}}}
- Write the file as soon as the pitches are read, then extend it in place with dur/off/meta.
- One entry per played notehead in reading order (system by system, left to right); x,y = notehead centre in
  PAGE pixels (±10 px). dur/off = fractions of a whole note (triplet 8th "1/12", grace "0"); off = onset from
  the start of the bar. Tied noteheads each keep their own dur/off with tie_from_prev on the continuation.
- Movement keys for meta.segments: use the key the orchestrator gave you for continuing movements and a short
  slug (e.g. "A3-finale") for any header you discover on the page.

## Then: bar segments for every bar — work/bars_pPAGE.json
Generate a starting point (after your notes exist):
```sh
~/venvs/dynamic/bin/python - <<'PYEOF'
import cv2, json, sys
sys.path.insert(0,'tools/dynamic')
from common import staves
from barlines import barlines, is_multirest
p=PAGE
im=cv2.imread(f'work/p{p}.png',0); B=im<140
d=json.load(open(f'work/final_p{p}.json'))
nxs={}
for n in d['notes']: nxs.setdefault(n['sys'],[]).append(n['x'])
out={}
for i,s in enumerate(staves(B),1):
    bl,x0,x1=barlines(B,s,nxs.get(i,[]))
    segs=[]; prev=x0
    for x in bl+[x1]:
        segs.append({"xa":round(prev),"xb":round(x),"label":"","multi":bool(is_multirest(B,s,prev,x))})
        prev=x
    out[str(i)]=segs
json.dump(out,open(f'work/bars_auto_p{p}.json','w'),indent=0)
print('systems',len(out))
PYEOF
```
Check with `bars_overlay.py PAGE` — stems are often detected as barlines; merge/split until every segment is a
real bar, then label each with its PAGE-LOCAL bar number (multi-bar rests as ranges "17–23", en dash). The
first segment of each system starts at the staff's left edge, the last ends at the right edge, and EVERY note
of yours must fall inside the segment carrying its bar number. Verify with
`bars_overlay.py PAGE work/bars_pPAGE.json`. Keep a "multi" key if helpful; labels are what matter.

## Quality bar
Go through every system. After writing final_pPAGE.json run `check.py PAGE`, look at ALL the overlay images,
fix misplaced/missing/extra notes and wrong pitches; then `check_rhythm.py PAGE` — fix overfull bars and real
overlaps (it cannot see rests, so underfull bars are fine). Deliberately hunt for cue-note contamination and
dropped accidentals before you finish.
