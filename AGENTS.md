# dynamic agent instructions

## Purpose and ownership

This repository holds reproducible score-reading data and static review artifacts. Reusable Fuyomi code, validators, schemas, and tests belong in `tools/`; composer/work/part-specific note data, timing, source hashes, reviews, and process receipts belong in `project/<composer>/<work>/<part>/`; static HTML/PDF derivatives belong in `public/`.

Do not import or write this repository's project data back into vEdit. The Fuyomi tool is standalone and must not depend on vEdit packages.

## Source and review boundary

- Original score PDFs, raw page scans, raw OMR bundles, private recordings, credentials, and machine-specific absolute paths are never committed.
- Preserve source PDF SHA-256 and physical page provenance without including the source file.
- Keep candidate detection, direct source observations, independent audit findings, and confirmed readings distinct.
- Structural or tool validation is not a note-level audit. Unresolved pitch, octave, accidental, cue, duration, tie, repeat, or alignment must remain flagged and excluded from playback paths that imply verification.
- Label annotated PDFs as derivatives. Do not claim synthetic practice audio is aligned to a recording without separate reviewed alignment evidence.

## Workflow

1. Inspect the active Issue, branch, repository state, and relevant project records before edits.
2. Preserve unrelated work and use a reviewable issue branch. Do not force-push, merge, or deploy without authorization.
3. Run the commands in `docs/testing.md` for the changed scope and record exact evidence.
4. Keep incomplete score audits in a draft PR with a handoff record; do not mark an unfinished transcription complete.

## Catalog and reproducibility

- `public/catalog.json` retains the composer-indexed guide catalog; `project/catalog.json` indexes the Fuyomi workflow artifacts and audit states.
- `python3 tools/build_catalog.py` builds both static catalogs. `python3 tools/validate_catalog.py` validates both catalogs, hashes, paths, source exclusions, and Fuyomi audit gates.
- Keep links repository-relative. No GitHub Pages deployment is configured.
