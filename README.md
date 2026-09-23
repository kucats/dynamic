# Dynamic Score Reading Catalog

A public catalog for score-derived reading guides. The catalog groups HTML pages and downloadable PDFs by composer, work, and instrument. Reusable catalog tools live in `tools/`; Fuyomi score reading itself is maintained in vEdit and is exposed through the thin adapter in `tools/fuyomi/`. Work-specific Python code and note data live in `projects/<composer>/<work>/`.

## Browse

Open [`public/index.html`](public/index.html) for the catalog. It includes Verdi's Nabucco Sinfonia Trombone II pages 2–4, Dvořák Horn II excerpts, and the existing Dvořák Symphony No. 8 Trombone I–III results. Each guide shows whether its note reading is reviewed or draft, lists limitations, and links to its PDF and any interactive reading HTML.

The site files are static. GitHub Pages is not configured in this change; the repository itself is the public publication location.

## Validate or rebuild

From the repository root, using Python 3.11 or later:

```sh
python3 tools/build_catalog.py
python3 tools/validate_catalog.py
python3 tools/fuyomi/publish.py build
python3 -m unittest discover -s tests
```

The catalog toolchain uses only the Python standard library. Rerendering the work-specific score PDFs additionally needs the listed source inputs, Pillow, ReportLab, and local fonts; raw score PDFs, OMR archives, scans, and audio are intentionally excluded.

## Review labels

- **Reviewed** means the printed playable noteheads were visually checked in the score. It does not mean independent performance or recording verification.
- **Draft** means some pitches, noteheads, voices, or possible cues still need checking.

All slide positions are practical starting positions, not intonation guarantees. See each guide's HTML page for its specific scope and caveats.

## Repository layout

```text
public/                                  Static HTML, catalog metadata, and PDFs
projects/<composer>/<work>/              Work-specific scripts and note data
tools/                                   Reusable catalog build, validation, and Fuyomi adapters
```

No license is declared in this repository. Public visibility does not grant reuse permission; add a license before inviting third-party reuse.
