# dynamic agent instructions

## Project identity

- **Project:** `kucats/dynamic`
- **Purpose:** Reproducible, reviewable data and static publications for music score reading.
- **Primary runtime:** Python 3.11+ for tools; static HTML/CSS/JavaScript for public artifacts.
- **Deployment target:** None configured; this repository publishes reviewable files only.
- **Current status:** Experimental.
- **Non-goals:** Hosting/deployment, source-score distribution, automatic approval of OMR, or claiming synchronized playback without reviewed timing.

## Ownership map

- `tools/`: reusable score-reading utilities, schemas, validators, tests, and instructions.
- `project/<composer>/<work>/<part>/`: composer/work/part-specific input identity, note data, timing, independent audits, and process receipts.
- `public/`: static catalog and reviewed HTML/PDF derivatives. Every linked artifact must resolve inside this repository.

The project data and generated artifacts are the source of truth for this repository. Do not require vEdit imports or write generated data back into vEdit.

## Source and review boundary

- Original score PDFs, raw page scans, raw OMR files, private recordings, and absolute local paths are never committed.
- Store the original PDF SHA-256, physical source-page references, tool versions, and review method as provenance.
- A derived annotated score may contain the limited source-page excerpts needed for its reading aid. Label it as a derivative and keep it separate from the raw source.
- Keep OMR candidates, direct source observations, independent audit findings, and confirmed readings distinct.
- A structural pass is not a note-level audit. An unresolved pitch, octave, accidental, cue identity, duration, repeat, or alignment must be flagged and excluded from any playback path that would assert it as verified.
- Do not describe synthetic practice audio as a recording match. Timing/playback is enabled only for reviewed note durations, rests, ties, and repeat paths.

## Workflow

1. Inspect the relevant Issue and branch before editing.
2. Make one reviewable change on the issue branch; preserve unrelated state.
3. Validate the exact modified scope with commands in `docs/testing.md`.
4. Open a draft PR while review findings or acceptance items remain unresolved.
5. Do not merge or deploy without explicit authorization.
