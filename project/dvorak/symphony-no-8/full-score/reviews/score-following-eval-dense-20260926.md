# Score-following evaluation with dense decode (all 21 parts) — 2026-09-26

Trial for issue #52 priority 1 (event/onset matching) and the question whether a
COMPLETE reference (all decoded parts) fixes the ~30% coverage bottleneck that
limited codex/experimental-score-following-4 (horn II + trombone I only).

Recording: Tama Central Park.m4a (user-supplied rehearsal recording, ~42 min,
phone-mic quality; not committed). Movement slices: I 0–760s, II 762–1374,
III 1374.5–1754, IV 1754–2510.

## Ground truth

`align_dense.json` anchors rebuilt for this eval: 12-dim chroma reference
synthesized from all 21 decoded parts on the reader score-time axis (0.2 s
frames), librosa global DTW vs CQT chroma of the audio. Verified spot check:
the one previously tracking-confirmed position (mvt I bar 298 @ audio 698.9 s)
matches the new anchor at 698.8 s. Bar-level is still "coarse" (± a few bars);
movement level is solid. These anchors replaced the earlier sparse-reference
anchors in `alignment-tampacentralpark.json`, whose mvt-I tail was polluted
(bar axis −5..389 vs real 318 bars — an old page-mapping bug injected
misrouted events; fixed source: filename page number is authoritative, not
`d.page`).

Round 2 added `alignment-tampacentralpark-hybrid.json`: same anchor layout,
built from the 24-dim hybrid feature DTW — currently the reference anchor
set (v1 kept for cross-method comparison).

## Methods tried and results

Accuracy = |estimated audio time − anchor audio time| at emitted positions.

| method | reference | I | II | III | IV |
|---|---|---|---|---|---|
| codex PhraseMatcher (32 s causal chroma window, multi-speed DTW) | dense-tutti | locked tail only; tracking positions med 2.3 s err | none | none | none |
| codex PhraseMatcher | dense-melody (fl/ob/cl/vn1) | none | none | none | none |
| codex PartPitchMatcher (harmonic) | per-part vn1/fl1/trb1 | candidates, no lock | — | — | — |
| codex EventSequenceMatcher | dense-tutti | bestRawQuality 0.677 vs gate 0.68 → 0 accepted | — | — | — |
| codex EventSequenceMatcher | per-part vn1/fl1/trb1 | rawQuality 0.20–0.45 | — | — | — |
| sliding-window chroma NCC, 30 s, multi-speed (0.5–2.0) | dense-tutti | 9–10 % @8 s (tempo-warped local windows still confused) | | | |
| event-seq global DTW, onset pc-sets (top-4 CQT) | dense-tutti | 3 % @8 s | 19 % @8 s, 40 % @20 s | **66 % @8 s, 100 % @20 s, med 5.2 s** | 6 % |
| event-seq global DTW, midi pitch sets | dense-tutti | 3 % | 0 % | 52 % @8 s, med 7.7 s | 7 % |
| event-seq subsequence (40-event windows) | dense-tutti | 1–7 % @8 s all mvts — short windows not discriminative | | | |
| banded tracker (24 s window, ±12 s radius, tempo prediction) | dense-tutti | 5–9 % coverage, locks onto wrong positions — local chroma gates can't distinguish look-alike passages | | | |

## Round 2 — more methods (hybrid feature, subseq DTW, IOI, contours)

New feature found: **hybrid 24-dim `[sustain chroma; per-pc attack novelty × 0.5]`**
— chroma alone captures sustained harmony but blurs attacks on phone audio;
adding an exponentially decaying (~0.4 s) per-pitch-class onset channel
sharpened the global DTW enough that it is now the best method AND the new
anchor source (`alignment-tampacentralpark-hybrid.json`).

Accuracy = |estimated − v1 chroma anchor| at each bar — i.e. for the hybrid
rows this measures **cross-method agreement between two independent DTW
alignments**, not self-agreement. Global (whole-movement) methods:

| method | I | II | III | IV |
|---|---|---|---|---|
| **hybrid global DTW w=0.5** | **med 3.6 s, 68 % @8 s, 77 % @20 s** | **med 2.4 s, 82 % @8 s, 92 % @20 s** | **med 3.0 s, 76 % @8 s, 100 % @20 s** | **med 11.6 s, 41 % @8 s, 79 % @20 s** |
| hybrid global DTW w=1.0 | med 3.4 s, 69 % @8 s | med 6.6 s | med 5.4 s | med 64 s |
| hybrid global DTW w=2.0 | med 12.2 s | med 26.8 s | med 18.6 s | med 57 s |
| pc-novelty-only DTW | med 45 s | med 51 s | med 9.4 s, 80 % @20 s | med 68 s |
| bass-contour DTW (lowest bin <~250 Hz) | med 91 s | med 42 s | med 30 s | med 32 s |
| melody-contour DTW (top bin) | med 50 s | med 49 s | med 40 s | med 227 s |
| onset-density envelope DTW | degenerate — fails | | | |

Local/causal acquisition methods (what realtime actually needs):

| method | result |
|---|---|
| banded tracker on hybrid feature (24 s win, ±12 s) | coverage 0–3 % — still cannot lock |
| subsequence DTW, 60 s hybrid windows ×10/mvt | 0 % @20 s all mvts; margins ≈0 — 60 s windows are NOT placeable on this audio |
| IOI rhythm-pattern NCC (30 onsets, tempo-normalized) | ≤17 % @20 s — fails |

## Conclusions (honest)

- Two INDEPENDENT global alignments (12-dim chroma DTW vs 24-dim hybrid
  DTW) agree within ~3–4 s median at bar level across all four movements
  (77–100 % within 20 s). That cross-method agreement is the strongest
  evidence so far that the dense anchors are trustworthy at ±a few bars.
- Dense reference fixes the codew bottleneck *partially*: the only reliable
  tracking now comes from global/chunked alignment, not short causal windows.
- Phone-mic tutti audio has too few clean onsets (≈1.5/s detected vs 3.6/s
  expected in mvt I) and blurred pc-sets for short-window localization.
- Event-sequence matching works where the texture is sparse/rhythmic
  (mvt III scherzo): it is a viable *component*, not a standalone solution.
- Cold start over a whole movement cannot rely on local match alone —
  consistent with codex's design: manual priority + multi-candidate
  acquisition + tempo-prediction during loss is the right architecture
  (#53's 「落ちた🎙️」 with region hints). Dense references now let every
  part supply a template, so acquisition can offer candidates from the
  player's own part plus tutti plus melody layer simultaneously.

## Next steps (in order)

1. ~~Banded tracker~~ tried (row above): pure local chroma tracking is too
   weak on this recording. The viable acquisition = periodic GLOBAL
   re-alignment of accumulated audio (one DTW per ~30 s of audio is cheap;
   incremental DTW variants exist for realtime), matching #53's
   手動指定優先 + 候補提示 design.
2. ~~Event matcher with bass + melody split channels~~ tried (round 2):
   bass/melody contours alone are too weak; onset-strength weighting DID
   pay off inside the hybrid feature. Remaining untried in this line:
   hybrid-feature event-DTW (attack-channel onset events only) and a
   coarse-to-fine acquire (global DTW on first ~2–3 min of buffered audio,
   then local maintenance).
3. Reader integration: WebAudio onset+pitch worker fed by the per-part
   following profiles already emitted for all 21 parts
   (`public/reader/following/dvorak8-*.json` in eval staging), with the
   periodic re-alignment loop as the acquisition mechanism.

Eval harness (work/, not committed): build_dense.py, build_anchors_v2.py,
build_anchors_v3.py (hybrid anchors), methods2.py, methods3.py,
banded_track.py, banded_track2.py, subseq_eval.py, ioi_eval.py,
event_eval.py, event_eval2.py, event_eval3.py, slide_eval.py, score_trace.py,
extract_slices.py; replay driver = codex tools/dynamic/following_replay.mjs.
