# 0001: Keep score-reading tools, project evidence, and public derivatives separate

- **Status:** Accepted for this repository
- **Date:** 2026-09-24

## Decision

Reusable score-processing code belongs in `tools/`, composer/work/part evidence belongs in `project/`, and browsable HTML/PDF derivatives belong in `public/`. Original source PDFs, full source scans, raw OMR files, private recordings, and machine-local paths stay outside the repository. Each reading record binds to the source PDF by SHA-256 and reports audit/playback status explicitly.

## Rationale

This keeps the workflow portable without coupling it to vEdit's larger engineering repository, makes the source provenance reproducible without redistributing scores, and prevents an OMR candidate or a structural pass from being presented as a verified reading. Playback must use reviewed durations/rests/ties and is disabled if note coverage is incomplete.

## Consequences

Fuyomi is packaged as a standalone Python module. Existing score work can be migrated as sanitized project JSON and annotated derivatives. Static index entries include artifact hashes and explicit limitations. Publication/deployment is not part of this decision.
