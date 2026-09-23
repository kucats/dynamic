# Architecture and invariants

## Data flow

```text
original score (external, immutable)
  -> page-render / OMR candidates (private working state)
  -> reviewed pitch and rhythm JSON (project data)
  -> structural validation and artifact build (tools/fuyomi)
  -> public HTML/PDF derivative with visible review status
```

`tools/fuyomi/` contains the standalone Fuyomi implementation ported from the vEdit score-reading workflow. The tool uses source hashes to bind review decisions to the exact PDF and candidate data; its workspace may contain source-page images and OMR files, so working workspaces must stay outside Git. The repository itself stores only reviewed project data and permitted derivative artifacts.

## Project organization

Each project is scoped under `project/<composer>/<work>/<part>/`. Keep separate files for note readings, duration/rest/tie data, source observations, and independent review. Record physical PDF page and printed part page separately. Use concert/written pitch and transposition explicitly. Confidence never substitutes for the independent source audit.

`project/catalog.json` is the machine-readable artifact and coverage index. `public/index.html` is a static view over that catalog. Generated links must be repository-relative; absolute local paths are prohibited.

## Playback authority

The player can sound notes only when their pitch and duration are explicit. Score-follow highlighting is driven from those same events. A movement with incomplete note or rhythm audit is marked unavailable for continuous playback; do not fill gaps with guessed durations or OMR defaults. The tone generator is a practice reference and is not aligned to any external recording unless a separately reviewed alignment is present.

## Provenance and privacy

Record source filename as bibliographic metadata only when useful, source SHA-256, page span, software versions, and time measurements. Do not commit original PDFs, unannotated source scans, raw OMR, private audio, local file paths, or workspace bundles that contain those files. Keep temporary workspaces ignored or outside the repository.

## Change records

Schema changes update the schema, validator, examples, documentation, and tests together. Non-trivial coverage or audit changes are tracked in GitHub Issues and reviewed in pull requests. No publishing or deployment is configured in this repo.
