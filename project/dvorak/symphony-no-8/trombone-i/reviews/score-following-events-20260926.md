# Event-sequence following experiment — 2026-09-26

Tracking: [#52](https://github.com/kucats/dynamic/issues/52). Product integration: [#53](https://github.com/kucats/dynamic/issues/53). This is an offline prototype and structural evaluation, not a score audit or reviewed recording-to-measure alignment.

## Data and scope

The user's phone recording remains primary: SHA-256 `60fdb0e11a6223aeb5ac7308655a411e265b2c4386baa04d1b9f36a8856641b8`, decoded duration 827.477333 s. Movement IV is assumed. The recorder associated with the reported near-trombone placement has not been confirmed. No private audio, path, feature array or fine-grained trace is published.

The generated Trombone I data and its existing playback timeline are unchanged. Uncertain notes are excluded. Valid, contiguous same-pitch ties extend the previous event; an orphan continuation does not invent an attack. Repeated occurrences retain separate positions. No missing written repeat is reconstructed.

## What changed

`tools/dynamic/following_events.mjs` turns the existing 49-dimensional harmonic evidence into causal event hypotheses: a new peak region must persist for two 200 ms frames. The complete feature vector remains available for pitch support. A rolling 32-second history supplies at most 24 events to subsequence edit alignment.

The alignment has explicit pitch-substitution cost, observation-insertion cost and score-deletion cost. Transitions allow up to two skipped events on each side. Timing uses the interval between aligned events, including all skipped events. Seven nominal speed hypotheses (0.5–2.0) receive a bounded interval-ratio penalty. Costs normalize by observed event count, without multiplying by the fraction of non-rest score frames. Synthetic time dilation checks this property; it does not establish fairness across all real passages.

Acceptance requires at least eight observations over four seconds, six supported matches, four distinct supported pitches, latest-event support and quality >= 0.68. The quality is an uncalibrated edit-cost statistic, not a probability and not directly comparable with the earlier frame-chroma scores. These gates precede the existing repeated-acquisition controller. Manual priority, gradual correction, last-BPM prediction and explicit-stop behavior are retained.

The new algorithm is **not loaded by the reader**. The shared controller recognizes the diagnostic candidate type; normal reader candidates and their thresholds are unchanged. CLI option `--features events` requires `--template part`. Error operations are already intrinsic to that option; `--tolerate-errors` remains specific to the previous harmonic diagnostic.

## Full-recording results

All conditions analyze the same 4,137 frames with 48 kHz mono mix, 8192-point Blackman FFT, 200 ms hop. The final sample-and-hold interval is clipped at the last analyzed sample. No independent measure labels exist for this recording.

| Condition | Eligible event-search updates | Best pre-gate edit quality | Candidate/accepted tracking |
| --- | ---: | ---: | --- |
| Original phone order | 404 / 905 | 0.3062 | none / 0 s |
| Frame shuffle, seed 94731 | 0 / 1,092 | unavailable | none / 0 s |
| Two-second block shuffle, seed 94731 | 439 / 935 | 0.1702 | none / 0 s |

The existing ensemble baseline previously entered acoustic tracking for 9.0 s, and part-only chroma for 3.6 s; neither was independently checked for correct bars. The event experiment has **not demonstrated a real-recording improvement**. The larger pre-gate score for original order is not an accuracy result. Gates were not lowered to inflate coverage.

Frame shuffle yielded at most five events per search and never passed the minimum-context gate. It is therefore a weak control for this segmentation frontend. The added two-second block shuffle preserves sustained local fragments and every source frame, including the final partial block, while destroying long-range order. It did reach the event-alignment stage, with no accepted candidate. One shuffled recording does not estimate a general false-acquisition rate.

Measure accuracy remains `null`. Zero backward changes reflects an explicit controller rule, not correctness. All positions remain unconfirmed. Processing was on a desktop; no mobile latency or power result is claimed.

## Structural evidence

- Nine added Node tests cover unresolved-note exclusion, tie continuation and repeats; causal two-frame segmentation; explicit substitution/deletion/insertion with elapsed time retained; sparse event timing; ambiguous repeated phrases; rejection of a static tone; manual priority and explicit stop; automatic synthetic acquisition and recovery after a six-second rest; pitch-order and two-second block controls.
- The original synthetic full replay contains wrong pitches, missing notes and a six-second rest. Known score-time error is asserted below one second at p95; this is a synthetic controller check, not ensemble bar accuracy.
- The direct edit-path fixture recovers one insertion, one deletion and one substitution. These labels describe the constructed example and must not be assigned to the user's playing without independent observation.
- No score notes, generated reader JSON, recording or source PDF changed.

Scoped validation:

- `node --test tests/reader/*.test.mjs`: **57 passed**, including the nine new event/control tests.
- `python3 tools/dynamic/validate_reader.py`: **4 reader parts valid**.
- `python3 tools/dynamic/build_following.py --check`: **all 4 profiles reproduce**.
- `node --check` passed for `public/reader/follow-model.mjs`, `follow-addon.js`, `follow.mjs`, `follow-worker.mjs`, `follow-alignment.mjs`, and `tools/dynamic/following_events.mjs`, `following_controls.mjs`, `following_part.mjs`, `following_replay.mjs`.
- `python3 -m py_compile tools/dynamic/evaluate_following.py` and `git diff --check`: passed.
- `python3 tools/dynamic/evaluate_following.py '<local-recording.m4a>' --template part --features events --out /tmp/part-events.json`: full-recording comparison, with the same command repeated using `--control shuffle` and `--control shuffle-blocks`; results above. Python requires NumPy. The local output retains detailed traces and is not committed.

## Next evidence and integration

1. Independently review a few phone-recording time/bar/occurrence anchors and a short sequence of audible attacks. This separates frontend extraction failure, score uncertainty and position ambiguity. Reference-audio time and proportional duration mapping are not ground truth.
2. Compare a shorter frontend hop and multiple event-boundary hypotheses. The current 200 ms peak-region segmentation cannot reliably resolve short notes or same-pitch rearticulation, and a peak may belong to another instrument. Merely tolerating more insertions is not sufficient evidence of improvement.
3. Regenerate from the corrected score and compare an unused recording. Calibrate false acquisition before enabling this algorithm in the reader.
4. Proceed with the local "lost here/before/after" search UX independently of acoustic model selection. Room voting needs fresh local evidence from different participants; prediction or received room votes must not recursively become new votes. See `docs/score-following-integration.md` for the staged integration and manual-priority contract.
