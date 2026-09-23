# Validation Contract

## Required local checks

Run from the repository root with Python 3.11 or later. The catalog builder, validator, and tests use the standard library and need no network access.

| Scope | Command | Expected result |
| --- | --- | --- |
| Build static HTML | `python3 tools/build_catalog.py` | Regenerates the catalog index, work page, per-reading HTML pages, and stylesheet |
| Validate catalog | `python3 tools/validate_catalog.py` | Exits zero only when required metadata, paths, links, excluded inputs, and SHA-256 values are valid |
| Unit tests | `python3 -m unittest discover -s tests` | Path traversal and SHA-256 format checks pass |

## PDF inspection

For a change that edits or regenerates a PDF, inspect its metadata/page count with `pdfinfo`, render pages with `pdftoppm`, and visually inspect representative pages plus every changed layout. Do not claim visual validation from text extraction alone.

## Evidence

The pull request should name the commit, Python version, commands, results, and any checks not run. Work-specific score renderers require their omitted source PDF/OMR inputs, source-page images, Pillow, ReportLab, and explicitly supplied local font files; those renderers cannot be fully regenerated from this public repository alone.
