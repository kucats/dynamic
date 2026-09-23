# dynamic agent instructions

## Purpose and ownership

This repository contains reproducible score-reading tools, per-work evidence, and static review artifacts. Reusable Fuyomi code, schemas, validators, and tests belong in `tools/`; composer/work/part-specific notes, timing, source hashes, reviews, and process receipts belong in `project/<composer>/<work>/<part>/`; static HTML/PDF derivatives belong in `public/`.

The Fuyomi engine is ported into this repository and must run without importing vEdit. Do not write project data back into vEdit.

## Source and review boundary

- Original score PDFs, raw page scans, raw OMR bundles, private recordings, credentials, and machine-specific absolute paths are never committed.
- Record the source PDF SHA-256 and physical page references without including the source itself.
- Keep candidate output, direct source observations, independent audits, and confirmed readings distinct.
- Structural or tool validation is not a note-level audit. Unresolved pitch, octave, accidental, cue, duration, tie, repeat, or alignment must remain flagged and excluded from playback paths that imply verification.
- Annotated PDFs are derivatives. Synthetic practice audio is not a recording match without separate reviewed alignment evidence.

## Workflow

1. Inspect the active Issue, branch, repository state, and relevant project records before editing.
2. Preserve unrelated work and use a reviewable issue branch. Do not force-push, merge, or deploy without authorization.
3. Run the commands in `docs/testing.md` for the changed scope and record exact evidence.
4. Keep incomplete score audits in a draft PR with a handoff record; do not represent unfinished transcription as complete.

## Catalogs and reproducibility

- `public/catalog.json` indexes composer/work guides and generated HTML/PDF; `project/catalog.json` indexes Fuyomi outputs and audit/playback states.
- `python3 tools/build_catalog.py` builds both static catalogs. `python3 tools/validate_catalog.py` validates both catalogs, hashes, paths, source exclusions, and audit gates.
- `tools/fuyomi/publish.py` is a convenience wrapper around those root commands.
- Keep links repository-relative. No deployment is configured.
