# Local reader following experiment — 2026-09-26

Related issue: #4. Starting reader commit: `73153a0`. Implementation branch: `codex/experimental-score-following-4`. This is an engineering experiment, not a score audit or verified recording alignment. No publication/deployment is part of this change.

## Primary recording experiment — v1 baseline

User-provided phone recording SHA-256: `60fdb0e11a6223aeb5ac7308655a411e265b2c4386baa04d1b9f36a8856641b8`. Decoded duration: 827.477333 s. Movement IV is an assumption for this experiment. No private audio or per-second derived trace is committed.

Replayed through `tools/dynamic/evaluate_following.py`, part `dvorak8-trombone1`, movement `IV`, using the actual `public/reader/follow-model.mjs`. The generated profile combines Horn II and Trombone I, excluding notes flagged uncertain. Analysis: mono mix, 48 kHz, 8192-sample Blackman FFT, 200 ms hops. This is offline replay, not evidence for an iPhone microphone/browser pipeline.

| State | Frames of 4,137 |
| --- | ---: |
| Listening / no accepted location | 1,290 |
| Candidates / no accepted location | 81 |
| Acoustic tracking | 6 |
| Tempo prediction | 2,760 |
| Backward changes of the score-progress coordinate | 0 |

The tracking fraction is about 0.15%, **not an accuracy score**. The raw heuristic accepted only a short stretch; almost all later movement was tempo prediction. There are no independently reviewed audio-to-measure labels, so measure accuracy remains unknown/null. Zero backward changes is a deliberate display constraint, not proof of correct location. This experiment does **not** establish usable autonomous ensemble tracking.

The rough measure suggestions previously obtained by scaling a reference recording's duration are not used as anchors, labels, or training data. Real improvement requires more complete ensemble evidence and reviewed per-measure alignment. Repeated themes leave multiple plausible locations; manual choice is an explicit user control, not an audit.

Observed desktop processing per input frame: median 0.0044 ms, p95 1.37 ms, maximum 9.50 ms. These timings include many cheap prediction/listening frames and exclude audio decode, UI, microphone acquisition and device scheduling. Do not extrapolate them to iPhone latency or battery life.

## Structural / interaction evidence

- `python3 tools/dynamic/validate_reader.py`: all 4 reader parts pass.
- `python3 tools/dynamic/build_following.py --check`: all 4 generated profiles reproduce. No generated reader note/image JSON was edited.
- `node --test tests/reader/follow-model.test.mjs`: 10 pass. Distinctive artificial phrase, polyphonic mixture with brief breaths, uncertain notes, repeated occurrences, manual priority, constant BPM across a nominal tempo change during loss, stop/resume audio clock, monotonic phase correction, no false static-tone acquisition, worker revision/generation fencing.
- Full reader Node suite: 37 checks (including the above). Artificial fixtures are not real ensemble accuracy evidence.
- Syntax checks: reader app, follow addon/model/UI/worker, tuner addon and service worker; Python compilation of builder and replay entry point. `git diff --check` clean.
- Local in-app browser at desktop and 390 × 844: enabled from Settings, local option and disabled remote option visible, microphone remains stopped on enable/reload; manual IV/170 displays rehearsal H with a measure overlay. Overlay survives bar-number layout re-render. Re-exploration, movement change and disabling clear it. Disabling hides the panel. No physical microphone permission was requested during this visual check.
- Physical iPhone/iPad capture, permission races on those devices, WAN/server transport, and independently labelled measure accuracy remain unverified.

## Handoff

Keep the feature explicitly experimental. User requirements are implemented in the display/control layer: manual override remains the origin, competing distant candidates do not relocate it, and loss continues at the last estimated quarter-note BPM with a dashed cursor and growing tentative region. Stop/disable intentionally stops prediction and releases capture. Remote mode must remain disabled until authentication, transport, privacy behavior and actual device results are reviewed.

## Long-duration follow-up — v2

The same phone recording was replayed in full (827.477333 decoded seconds) after replacing independent short-window acquisition with bounded causal context DTW. After 12 seconds of context, the matcher uses at most the preceding 32 seconds, allows local tempo variation, retains interior rests, and requires successive advancing candidates. The DTW recurrence gives equal cost weight per query frame for all step types. A matching acoustic candidate only confirms the displayed cursor after phase correction has brought them together. Prediction, manual priority and no automatic distant relocation are preserved.

The current Horn II + Trombone I template has nonzero pitch masks in **30.20% of its uncompressed movement-IV timeline** (607 / 2,010 frames). This is score-template coverage, not the percentage of audible music or the percentage of correct notes. More complete, correctly aligned ensemble parts would supply evidence in many currently unsupported regions. Correcting only the visible score image does not add such structured evidence.

| Reader replay | v1 | v2 |
| --- | ---: | ---: |
| Listening frames | 1,290 | 1,218 |
| Candidate-only frames | 81 | 1,524 |
| Acoustic-tracking frames | 6 | 45 |
| Acoustic-tracking frame equivalents | 1.2 s | 9.0 s |
| Tempo-prediction frames | 2,760 | 1,350 |
| Longest uninterrupted acoustic-tracking span | not measured in v1 | 6.6 s |
| Backward score-progress changes | 0 | 0 |
| Independently labelled measure accuracy | unknown | unknown |

The v2 uninterrupted span starts at phone time 548.515 s and ends at 555.115 s. These timestamps describe heuristic state intervals, **not verified bar anchors**. The stronger acquisition gate delayed accepting a location; reducing prediction time does not by itself imply better accuracy. The result is still insufficient for reliable autonomous ensemble score following. The phone recording was used during development; it is not a held-out evaluation.

### Independent-performance diagnostic

Reference: Dvořák Symphony No. 8, movement IV, DuPage Symphony Orchestra / Barbara Schubert, [Wikimedia Commons source and licensing page](https://commons.wikimedia.org/wiki/File:Dvo%C5%99%C3%A1k,_Antonin_%E2%80%94_Symphony_No._8,_Op._88_%E2%80%94_4._allegro.ogg). The Commons page identifies CC BY 3.0 US. Reference file SHA-256: `cd285f930b43ba6638eb42b4c10c41b5052a388b7be274173b6421241f4aa59a`; decoded duration 605.387771 s. Reference audio and extracted features remain outside the repository. No endorsement is implied.

The phone recording and this independent performance were compared using the **same JS chroma and DTW recurrence** as the score experiment. Input is consumed causally; the complete reference is known in advance. This diagnostic reports reference-audio seconds only and always leaves `score_position=null, confirmed=false`. It has no reader page-navigation path.

| Reference diagnostic | Tracking-candidate sample intervals | Longest uninterrupted interval |
| --- | ---: | ---: |
| 32-second history | 311 s | 234 s |
| 8-second history, otherwise identical settings | 315 s | 234 s |
| 32-second history, deterministically shuffled phone feature order | 0 s | none |

Both original-order runs have the same longest span: phone time 286.915–520.915 s (1-second update intervals). The last accepted update is at 519.915 s. The candidate reference path progresses from about 305.915 s to 548.715 s over those accepted updates. This demonstrates sustained **cross-performance acoustic matching**, not independently audited score alignment. The short-window comparison does **not** show an advantage for 32 seconds on this recording. The longer-window benefit is separately demonstrated by the original artificial repeated-motif regression, where the last 8 seconds are identical but preceding context differs.

The shuffled control keeps timbres/pitch distribution but destroys musical order (Fisher–Yates, fixed seed 94731). Zero accepted spans on this one control is not a general false-positive-rate estimate. There is no claim of held-out generalization, movement-classification accuracy or measure accuracy.

### Reproduction and checks

Use `evaluate_following.py` with the primary recording and `--out` outside the repository. Add `--reference` for reference-only diagnostics; compare `--reference-window 8` and `--reference-control shuffle`. Exact command shapes are in `docs/score-following-reader.md`. Traces use FFT-window-center timestamps; each frame becomes available 85.333 ms later. Timings exclude decoding, device scheduling, microphone permission and rendering. In the final desktop run, score processing p95 was 2.285292 ms per input frame and 32-second reference alignment p95 was 22.135584 ms per update; concurrent diagnostics were running, so these are not controlled device benchmarks.

New regression coverage: 3 minutes of variable-tempo original synthetic input, 4-second capture loss followed by reacquisition, bounded 161-frame history, unchanged emitted prefix when future input is added, identical short motifs distinguished by long context, silence retaining tempo without being counted as tracking, missing capture intervals, fair DTW normalization, uninterrupted-span reporting, and rejection of stale profiles after pitch/repeat edits even with the same source-PDF hash.

Schema-2 following profiles include the selected part's timeline and are checked against its actual notes before use. A score revision needs `build_reader.py` / `refresh_reader_pitches.py`, then `build_following.py`. Public score JSON itself was not hand-edited. The app remains local, opt-in and experimental; remote is disabled. Full-score audit, real iPhone/iPad microphone evaluation, and independently reviewed measure labels remain outstanding.

Final checks after the v2 changes:

- `node --test tests/reader/*.test.mjs`: **44 passed**, including 17 following regressions.
- `python3 tools/dynamic/validate_reader.py`: **4 parts passed**.
- `python3 tools/dynamic/build_following.py --check`: **4 profiles reproduced**.
- `node --check` on follow model/alignment/worker/UI/addon, reader app, service worker and both replay/metrics modules: passed. `python3 -m py_compile` on builder/evaluator: passed. `git diff --check`: passed.
- Reopened the local browser after changes: local microphone remained stopped, remote remained disabled, manual movement-IV bar 170 displayed rehearsal H and its blue measure highlight. No browser errors were reported. No physical microphone capture was initiated.
- No private audio, feature arrays, per-second traces, machine paths, source PDFs or page scans were added to repository files. No commit, push or deployment was made in this follow-up.
