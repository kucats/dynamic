# Architecture

## Purpose

This repository publishes score-derived study material as a static composer-indexed catalog. It stores annotated PDF outputs and matching HTML pages separately from the Python scripts and note data used to prepare them.

## Components

| Component | Responsibility | Interface |
| --- | --- | --- |
| `public/catalog.json` | Catalog source of truth: composer/work/instrument labels, review state, caveats, source hashes, artifact paths, and artifact hashes | JSON schema version 1 |
| `public/` | Static catalog index, work page, per-reading HTML pages, stylesheet, and downloadable PDFs | Relative links; no server-side code |
| `tools/build_catalog.py` | Generate static HTML and CSS from the catalog JSON | `python3 tools/build_catalog.py` |
| `tools/validate_catalog.py` | Validate required metadata, paths, generated links, hashes, and publication exclusions | `python3 tools/validate_catalog.py` |
| `projects/<composer>/<work>/` | Work-specific note data, extraction/render scripts, and reproduction notes | Python CLI; requires the documented local inputs |

## Data flow

A work project records the score and OMR input hashes, the resulting note JSON/CSV, and review caveats. Selected PDF artifacts are copied into `public/`. `public/catalog.json` maps those files to their composer, work, instrument, and generated HTML page. The build tool renders static pages; the validator checks that all repository-relative paths resolve, artifact hashes match, and each page links to the expected PDF.

The catalog never downloads inputs or calls external services. Missing paths, invalid hashes, or stale artifact bytes fail validation. Static pages require no JavaScript or third-party assets.

## Boundaries and invariants

- Raw source score PDFs, OMR archives, rendered input scans, audio, credentials, private logs, and machine-specific absolute paths stay out of public content.
- Every public reading has a visible `reviewed` or `draft` state and a non-empty list of limitations.
- Source hashes identify excluded inputs; artifact hashes identify included output files.
- Composer/work project code stays under `projects/`; reusable repository tools stay under `tools/`.
- A score-derived candidate is not represented as recording-verified unless that check is actually performed.

## Hosting

The repository is intended for public GitHub access. The `public/` directory is static content; GitHub Pages configuration and deployment are out of scope for the current catalog change.
