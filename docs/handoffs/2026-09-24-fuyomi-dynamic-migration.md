# Fuyomi score-reading migration handoff

## Tracking

- Repository: `kucats/dynamic`
- Issue: #1, https://github.com/kucats/dynamic/issues/1
- Branch: `agent/issue-1-fuyomi-catalog`
- Existing PR: #2, https://github.com/kucats/dynamic/pull/2
- Base before integration: `20bb4610b585765642b2a848b64405baa675c162`
- Existing PR head integrated without force-push: `d72052077af6dcf2470302b510b0f262109cce17`
- Fuyomi port commit: `0f67f88`
- Integration commit: `fc9d001fbb178449f57a5bcfb1708bb0eb6bcb95`

## Completed

- Ported the reusable Fuyomi workflow into `tools/fuyomi/`, without importing vEdit code at runtime.
- Combined the previous composer catalog and Fuyomi catalog builders and validators behind `tools/build_catalog.py` and `tools/validate_catalog.py`.
- Moved prior Dvořák trombone note data and render/transcription scripts from the plural project tree into `project/dvorak/symphony-no-8/`; score-specific and audit records now use the singular `project/` root.
- Kept derived score-reading PDFs and HTML under `public/`, retained the previous trombone catalog, and added Dvořák Horn II and Verdi Nabucco audit/status records.
- Excluded original scores, raw scans, raw OMR, private recordings, and machine-local paths.

## Validation evidence

On Python 3.12.14 with Pillow 12.3.0, pypdf 6.10.0, and ReportLab 4.4.9:

- `python3 tools/build_catalog.py` — pass.
- `python3 tools/validate_catalog.py` — pass; 6 Fuyomi items and 9 artifacts verified, composer catalog paths/links/hashes valid, Horn II playback fail-closed.
- `python3 -m unittest discover -s tests -v` — 17 passed.
- `python3 -m compileall -q tools tests` — pass, with cache output directed outside the repository.
- `node --check tools/fuyomi/player.js` — pass.
- `python3 -m tools.fuyomi --help` — pass.
- `git diff --check` — pass.

The inherited PDF review checked representative pages for the large-label Trombone II guide, four-page same-pages excerpt, Trombone III trial PDF, and provisional Nabucco PDF. No original score PDF was copied into the repository.

## Unresolved score work and stop boundary

- Dvořák Horn II has independent source audits for all four movements, but complete note/rhythm transcriptions remain unfinished. Continuous playback is disabled. The older Movement I and III exports are explicitly archived as superseded.
- Nabucco Trombone II pages 2–4 remain provisional OMR candidates; B-natural/sharp review and rhythm validation are incomplete. Playback is disabled.
- Trombone I/III and the combined trombone player retain their stated draft/trial limits. No recording-aligned playback is claimed.
- Keep PR #2 in draft until the remaining score audits and reviewer acceptance are complete. Do not merge or deploy without authorization.

## Next safe steps

1. Update PR #2 title/body to describe the Fuyomi migration, both catalogs, moved Dvořák project sources, and unresolved audit gates; convert it to draft.
2. Update Issue #1 with the final branch head and validation evidence, leaving it open for Horn II/Nabucco review work.
3. Continue note-level source audits and only enable playback after pitches, durations, rests, ties, and repeats pass independent review.
