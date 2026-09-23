# Architecture and invariants

## Data flow

```text
external immutable score PDF
  -> private page render / OMR candidates
  -> composer/work/part review data under project/
  -> reusable validation and artifact build under tools/
  -> static review HTML/PDF under public/
```

`tools/fuyomi/` is the standalone implementation ported from the vEdit Fuyomi special mode. It binds review decisions to source hashes and may use local score images/OMR in private workspaces. Those inputs remain outside Git. The workflow does not import or execute vEdit.

## Catalogs and ownership

`public/catalog.json` indexes composer/work guides, limitations, source hashes, and public HTML/PDF files. `project/catalog.json` indexes Fuyomi artifacts, source-page spans, audit status, and playback authorization. Root build/validate commands operate on both catalogs.

Reusable code, schemas, validators, and tests live in `tools/`. Composer/work/part readings, timing, reviews, and process receipts live under `project/<composer>/<work>/<part>/`. Static HTML/PDF derivatives live under `public/`. Raw source PDFs, raw scans, OMR, audio, and machine-specific paths are excluded.

## Playback authority

A player may sound notes only when pitch and duration are explicit. Score focus uses the same events. An incomplete note, rhythm, tie, or repeat audit blocks continuous movement playback. Synthetic audio is a practice reference; it is not aligned to an external recording without separate reviewed timing evidence.

## Validation and provenance

Keep candidate output, direct source observations, independent audits, and confirmed readings separate. Store source SHA-256 and physical page references, not the excluded source itself. A data-structure change updates schema, parser/validator, documentation, examples, and tests together. No deployment is configured.
