# Architecture and invariants

## Data flow

```text
external immutable score PDF
  -> private page render / OMR candidates
  -> composer/work/part review data under project/
  -> reusable validation and artifact build under tools/
  -> static review HTML/PDF under public/
```

`tools/fuyomi/` is the standalone implementation ported from the vEdit Fuyomi special mode. It binds review decisions to source hashes and can use local score images/OMR in private workspaces. Those inputs remain outside Git. No code imports vEdit.

## Catalogs and ownership

`public/catalog.json` indexes the existing composer/work guide collection and its project-source files. `project/catalog.json` indexes Fuyomi artifacts, source-page spans, audit status, and playback authorization. Both are generated/validated by the root catalog commands.

Reusable code, schemas, validators, and tests live in `tools/`. Composer/work/part-specific readings, timing, reviews, and process receipts live under `project/<composer>/<work>/<part>/`. Static HTML/PDF derivatives live under `public/`. Raw source score PDFs, raw scans, OMR, audio, and machine-specific paths are excluded.

## Playback authority

A player may sound notes only when pitch and duration are explicit. Score focus uses the same events. An incomplete note, rhythm, tie, or repeat audit blocks continuous movement playback. Synthetic audio is a practice reference; it is not aligned to an external recording unless separate reviewed timing evidence says so.

## Validation and provenance

Keep candidate output, direct source observations, independent audits, and confirmed readings separate. Store source SHA-256 and physical page references, not the excluded source itself. A change to data structure must update schema, parser/validator, documentation, examples, and tests together. No deployment is configured.
