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
| Patch hygiene | `git diff --check` | No whitespace errors |

For changed PDFs, inspect page count/metadata, render representative pages, and visually check changed layouts. Code validation does not certify a musical reading. Each artifact retains its source-bound audit scope, unresolved items, and playback state. Never mark an incomplete audit complete because software tests passed.
