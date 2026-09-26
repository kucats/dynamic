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

## Conclusions (honest)

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
2. Event matcher with better obs features: onset-strength weighting, bass +
   melody split channels (bass onsets are steadier in tutti). mvt III shows
   the event-DTW path works when texture is sparse.
3. Reader integration: WebAudio onset+pitch worker fed by the per-part
   following profiles already emitted for all 21 parts
   (`public/reader/following/dvorak8-*.json` in eval staging).

Eval harness (work/, not committed): build_dense.py, build_anchors_v2.py,
event_eval.py, event_eval2.py, event_eval3.py, slide_eval.py, score_trace.py,
extract_slices.py; replay driver = codex tools/dynamic/following_replay.mjs.
