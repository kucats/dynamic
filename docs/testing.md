# Validation contract

## Required checks

| Scope | Command | Expected result |
| --- | --- | --- |
| CLI | `python -m tools.fuyomi --help` | Lists standalone Fuyomi commands without importing vEdit |
| Python unit tests | `python -m unittest discover -s tests -p 'test_fuyomi.py' -v` | All available tests pass; optional dependency skips are reported |
| Syntax | `python -m compileall -q tools/fuyomi tests` | No Python syntax errors |
| JavaScript syntax | `node --check tools/fuyomi/player.js` | No JavaScript syntax errors |
| Project/catalog integrity | `python tools/validate_catalog.py` | Relative paths, hashes, coverage states, and source policy pass |
| Patch hygiene | `git diff --check` | No whitespace errors |

For changes to PDF/HTML generation, install `Pillow`, `pypdf`, and `reportlab` and run the full end-to-end workflow tests. Inspect generated PDF page count and a rendered page image; inspect the HTML in a browser and exercise play/pause, seeking, movement selection, and note highlighting. Any environment-based skip must be recorded in the PR.

## Music review is separate

Code validation proves data structure and behavior only. Each score publication needs source-bound note review, rhythm review where playback is offered, and an independent audit. Record the audit scope, note count, unresolved items, and resulting playback state in that project's `reviews/` files. Never change an unresolved audit to complete because a tool test passed.
