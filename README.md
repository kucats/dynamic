# dynamic

A small, reviewable catalog for score-reading workflows. Reusable processing code lives in [`tools/`](tools/); per-composer and per-work evidence lives in [`project/`](project/); static HTML/PDF outputs live in [`public/`](public/).

## Browse

Open [`public/index.html`](public/index.html) locally for the current catalog. The index links only to artifacts stored in this repository and shows each part's audit/playback status.

## Reproduce

Fuyomi is a standalone tool; it does not import vEdit. Use Python 3.11+ and install `Pillow`, `pypdf`, and `reportlab` for image/PDF operations. Audiveris and Poppler are optional external tools for candidate recognition and page rendering.

```sh
python -m pip install Pillow pypdf reportlab
python -m tools.fuyomi --help
python -m unittest discover -s tests -p 'test_fuyomi.py' -v
```

See [`tools/fuyomi/README.md`](tools/fuyomi/README.md) and [`docs/architecture/README.md`](docs/architecture/README.md). A passing tool test does not certify a score transcription; the project-level audit record remains authoritative.

## Source policy

The repo stores source hashes and bibliographic/page provenance, not source score PDFs, raw score scans, raw OMR caches, private recordings, or machine-specific paths. Annotated PDFs are derivative review aids and are kept under `public/artifacts/`.
