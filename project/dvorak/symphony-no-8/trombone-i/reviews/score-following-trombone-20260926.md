# Trombone-only / imperfect-performance follow-up — 2026-09-26

Tracking issue: [#52](https://github.com/kucats/dynamic/issues/52). Baseline reader commit: `34a21ed`. This is a local diagnostic experiment, not a note audit or reviewed audio-to-measure alignment.

## Request and data

The user reports a microphone in front of the trombone and an imperfect performance with wrong or unplayed notes. The phone recording remains the requested primary source. Which recorder was in that position has not yet been confirmed; no microphone-placement or instrument-isolation ground truth is inferred from this experiment.

Primary audio SHA-256: `60fdb0e11a6223aeb5ac7308655a411e265b2c4386baa04d1b9f36a8856641b8`. Full decoded duration: 827.477333 s. Movement IV is assumed. No private audio, private path, waveform, feature array or fine-grained trace is included here.

The available Trombone I movement-IV notes contain 268 usable events (uncertain notes excluded), sounding MIDI 50–67. They cover 394 / 2,010 template frames, or 19.60% of the score-time axis, compared with 607 / 2,010 = 30.20% for Horn II + Trombone I. These percentages do not measure audible-instrument prevalence, correct playing or note-audit completion.

## Controlled comparisons

Each case replays the full recording with the same causal position controller and acceptance gates. FFT and time conventions match the existing reader experiment: 48 kHz, 8192 Blackman, 200 ms hop, FFT-center timestamps; availability is 85.333 ms later. Left/right experiments use the selected channel before analysis; they do not select whichever channel happens to look better per frame. Reference audio is not used by any of these score-template cases.

| Template / feature / channel | Acoustic-tracking state total | Longest uninterrupted span |
| --- | ---: | ---: |
| Horn II + Trombone I / chroma / mix (baseline) | 9.0 s | 6.6 s |
| Trombone I / chroma / mix | 3.6 s | 1.8 s |
| Trombone I / chroma / left | 0 s | none |
| Trombone I / chroma / right | 0 s | none |
| Trombone I / harmonic register / mix | 0 s | none |
| Trombone I / harmonic register + capped negative evidence / mix | 0 s | none |
| Trombone I / harmonic register + capped negative evidence / left | 0 s | none |
| Trombone I / harmonic register + capped negative evidence / right | 0 s | none |
| Trombone I / chroma / shuffled mix (negative control) | 0 s | none |
| Trombone I / harmonic register + capped negative evidence / shuffled mix | 0 s | none |

All cases have zero backward score-coordinate changes because that is an explicit display constraint. Measure accuracy remains **unknown/null** in every case. The nonzero state totals do not prove correct bars; zero means the current gates did not accept a location, not that no trombone was audible. There is no demonstrated improvement to promote into the reader. This recording was used for development and is not held out.

## Prototype and limits

`tools/dynamic/following_part.mjs` supplies a diagnostic frontend with 49 register-preserving pitch hypotheses (MIDI 36–84). Each accumulates local spectral contrast from harmonics 1–6. Multiple hypotheses survive; a peak is not labelled as a played trombone note. This is neither source separation nor learned instrument identification.

The error-tolerant variant caps negative alignment evidence at zero, while missing evidence still receives no positive match reward. The latest-support gate uses the unmodified similarities. It inherits bounded timing warp, sticky manual position, gradual phase correction and last-tempo prediction. It does not implement a full insertion/deletion/substitution event model. Its diagnostic feature type and parameters are not enabled by the reader.

Applying unchanged gates to a differently scaled feature is a conservative initial comparison, not proof that harmonic features or single-part following cannot work. Additional calibration needs independent labels and held-out recordings; lowering thresholds merely to obtain longer tracking is not an accuracy result.

## What can be done next

1. Follow a sequence of **played note attacks and inter-onset intervals**, with explicit states for wrong, missing and extra notes. Keep several nearby hypotheses through a mistake and ask for fresh corroborating notes before accepting a location. Do not identify every unexpected note as a user error: it may be another player or an extraction error.
2. Revisit scoring for sparse parts. Current window-wide scoring combines note support with supported duration, so dense passages can outrank sparse passages. This is a design concern, not a verified diagnosis of any particular phone-recording bar. Compare event-based and activity-normalized scoring with false-acquisition controls.
3. Use the last accepted tempo through rests; reacquire at the next entrance. A long silent Trombone I passage contains no fresh trombone evidence. Ensemble context may help there when reliable, but must not override manual position.
4. Create a small, separately reviewed private set of audio-time/bar/repeat anchors, including wrong notes and rests. Then measure bar accuracy, false acquisition, reacquisition delay and prediction-only time. Neither reference-audio seconds nor proportional duration mapping supplies these labels.
5. Record microphone placement/recorder/channel, incorporate corrected structured score data, and evaluate another recording plus actual iPhone/iPad capture.

Background: [Nakamura, Nakamura and Sagayama, Real-Time Audio-to-Score Alignment (2016)](https://eita-nakamura.github.io/articles/TNakamura_etal_AudioScofo_ACMIEEE_TASLP_2015.pdf) models substitution, deletion and insertion errors in monophonic performance. The present diagnostic is not a reproduction of that paper and does not transfer its clarinet results to an ensemble trombone recording.

## Reproduction / structural evidence

Run `tools/dynamic/evaluate_following.py` with `--template part`; compare default `--features chroma` against `--features harmonic`, optionally `--tolerate-errors`. Add `--channel left` / `right`, and `--control shuffle` for the fixed-seed negative control. The default remains the existing ensemble/mix/chroma path. Exact command examples are in `docs/score-following-reader.md`. Output must stay outside the repository.

- `node --test tests/reader/*.test.mjs`: 48 passed, including 4 new diagnostic checks.
- Original synthetic brass spectra with a weak fundamental retain its octave as the strongest hypothesis in the five tested pitches. Flat spectra and silence return no feature.
- Original two-minute synthetic performance with wrong semitones, omitted notes, extra short sounds and four seconds of missing sound retains the known path within the asserted p95 < 1 score-second bound and reacquires; this is not real-instrument evidence.
- A static wrong sound cannot acquire a position. Following manual override it remains prediction-only and continues tempo.
- `python3 tools/dynamic/validate_reader.py`: all 4 parts pass. `python3 tools/dynamic/build_following.py --check`: all 4 profiles reproduce. No score notes or generated reader JSON were edited.

The reader's active feature extraction, thresholds, manual-priority behavior, local-only mode and prediction behavior remain unchanged. The shared DTW recurrence exposes a diagnostic option with the original default. Remote enablement and product-accuracy acceptance remain tracked in #52.
