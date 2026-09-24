# Validation contract

Run from the repository root with Python 3.11 or later. Catalog commands operate offline. PDF rendering additionally needs Pillow, pypdf, and ReportLab; Audiveris and Poppler are optional for candidate recognition and source-page rendering.

| Scope | Command | Expected result |
| --- | --- | --- |
| Rebuild both catalogs | `python3 tools/build_catalog.py` | Regenerates composer/work pages and Fuyomi landing page from both manifests |
| Validate both catalogs | `python3 tools/validate_catalog.py` | Checks metadata, repository paths, hashes, generated links, source exclusions, and audit gates |
| Unit tests | `python3 -m unittest discover -s tests -v` | Catalog safety and Fuyomi workflow/player tests pass |
| Fuyomi CLI | `python3 -m tools.fuyomi --help` | Shows standalone commands without importing vEdit |
| Python syntax | `python3 -m compileall -q tools tests` | No syntax errors |
| Player JavaScript | `node --check tools/fuyomi/player.js` | No syntax errors |
| DYNAMIC reader data | `python3 tools/dynamic/validate_reader.py` | Notes sit in numbered bars, timelines cover all notes, no path leaks |
| DYNAMIC reader JavaScript | `node --check public/reader/app.js && node --check public/sw.js` | No syntax errors |
| Cloudflare Worker asset scope | `npx wrangler deploy --dry-run` | Validates Worker config and uploads files from `public/` only |
| Score following tests | `cd tools/score_following && python -m pytest -q` | Unit/security plus real localhost WebSocket and WebRTC/Opus paths pass |
| Score following browser | `cd tools/score_following && python -m scorefollow serve --dev`, then `python scripts/browser_smoke.py` | Synthetic PCM/WebRTC, controls, and mobile-layout evidence; report compatibility capture separately |
| Score following benchmark | `cd tools/score_following && python -m scorefollow benchmark evidence/local` | Reproducible original-synthetic scenarios; never report them as real-instrument accuracy |
| DYNAMIC print PDFs | serve `public/`, then `python3 tools/dynamic/render_pdfs.py` | A3 PDFs regenerated; inspect representative pages |
| Patch hygiene | `git diff --check` | No whitespace errors |

For changed PDFs, inspect page count/metadata, render representative pages, and visually check changed layouts. Code validation does not certify a musical reading. Each artifact retains its source-bound audit scope, unresolved items, and playback state. Never mark an incomplete audit complete because software tests passed.
