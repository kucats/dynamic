# Validation / 2026-09-24

## Source boundary

Additive `tools/score_following/` implementation for kucats/dynamic #4 / PR #5.
Repository base: `dc3967b5829e8274a8a02f7cea5ede0231934437`.
No changes to the existing reader, original PDFs, audited score assets, or production deployments.

## Executed locally

- Python 3.13.5, Linux x86_64; exact installed dependency versions in `constraints-py313.txt`.
- `python -m pytest -q --junitxml=evidence/junit.xml`: **67 passed**, one upstream Starlette/httpx deprecation warning; initial full run 20.28 s. Raw summary and JUnit included in delivery ZIP.
- Includes actual localhost paced PCM WebSocket and aiortc ICE/DTLS/Opus audio reception, continuous resampling, note following, position DataChannel, re-anchor and peer cleanup. These are not mocked signaling tests.
- `python -m ruff check scorefollow tests scripts`: PASS. JavaScript `node --check`: PASS.
- Wheel build, installation in a clean venv, packaged web asset lookup and app creation from outside the source directory: PASS.
- Existing repository: `python -m unittest discover -s tests -v`: **23 passed**. `python tools/validate_catalog.py`, `python tools/dynamic/validate_reader.py`, compileall and existing reader/player JavaScript syntax checks: PASS.
- Existing DYNAMIC import: Horn III / III (55 events), Horn II / II (110), Horn II / III (63): structurally imported as **unreviewed**. Horn II / I and IV: rejected because unresolved `unc` remains. No note-level audit or actual recording match is claimed.

## Original synthetic benchmark

See `benchmark-summary.csv`; full metrics and traces are produced by `python -m scorefollow benchmark evidence/local`. Full measured metrics are also included in the delivery ZIP.

| Scenario | All voiced-frame exact ID | After first 200 ms | Detected notes |
|---|---:|---:|---:|
| Clean | 90.0% | 100.0% | 16/16 |
| Noise | 90.3% | 100.0% | 16/16 |
| Tempo 0.7 | 94.8% | 100.0% | 16/16 |
| Tempo 1.3 | 85.0% | 100.0% | 16/16 |
| Detune +28 cents | 89.4% | 100.0% | 16/16 |
| Pause 2 seconds | 90.0% | 100.0% | 16/16 |
| Restart and skip | 74.1% | 83.1% | 14/17 |
| Arbitrary start (index 8) | 78.7% | 86.8% | 7/8 |

The post-attack metric deliberately excludes the initial 200 ms of each labeled note and must not be reported as overall accuracy. Null/uncaptured positions count as misses. First-correct detection is not stable-lock latency. Confidence is uncalibrated. These are original synthesized tones, not recordings of a real instrument.

## Browser and deployment boundaries

Local Chromium 140 / Playwright 1.55 starts and reaches HTTP/WS authentication, but the isolated runtime fails font/rendering and AudioWorklet initialization (GPU/ANGLE errors and module initialization timeout). This is **BLOCKED locally**, not a browser test pass. The PR includes a read-only CI workflow to run `scripts/browser_smoke.py` on Ubuntu and upload its actual result/screenshots. Refer to the specific PR run for subsequent results; no success is implied by the workflow existing.

Docker build, WAN/TURN relay, Safari/iPhone hardware audio, live microphone recording, ensemble/source separation, concurrent production load and independent security audit: **NOT RUN**. No deployment performed.
