# Fuyomi standalone score-reading tool

This is the reusable score-reading workflow ported from the vEdit Fuyomi special mode. The engine and review steps are implemented in this repository and do not require a vEdit installation.

## Pipeline

1. `init` binds an external source PDF by SHA-256 and renders selected physical pages into a local workspace.
2. `recognize` runs Audiveris as a candidate generator, caching each page by input and engine hashes. Or use `import-omr` for saved page-level OMR candidates.
3. `review` provides candidate IDs outside the original staff. Human corrections are stored separately from candidates.
4. The reviewer fills pitch corrections and exact duration/rest/tie tokens; `build` performs structural checks and writes score JSON, review audit, HTML player, CSV, and annotated PDF.
5. `validate` checks source/candidate bindings and generated output hashes. `bundle` creates a private reproduction bundle and may include source images/OMR; do not commit such bundles.

OMR grade is only a candidate-quality measure, not a probability of a correct note. A `source_checked` flag is a recorded source review, not a listening or second-person audit.

## Commands

```sh
python3 -m pip install Pillow pypdf reportlab
python3 -m tools.fuyomi fuyomi init --source /path/to/score.pdf --out /tmp/reading --pages 2-5 --title 'Work' --part 'Part' --clef BASS --fifths 0 --meter 4/4
python3 -m tools.fuyomi fuyomi recognize /tmp/reading --audiveris /path/to/audiveris --engine-version 'Audiveris version'
python3 -m tools.fuyomi fuyomi review /tmp/reading
python3 -m tools.fuyomi fuyomi build /tmp/reading
python3 -m tools.fuyomi fuyomi validate /tmp/reading --source /path/to/score.pdf
python3 tools/fuyomi/publish.py build
```

Workspaces include source-page images and OMR files. Keep them outside the Git checkout. Project data records source hashes/page references and reviewed results; original PDFs and raw OMR are not published.

## Conventions and limits

Pitches use scientific pitch internally (`B3`), display `H3` for B-natural, and retain `Bb3` for B-flat. `C4` is middle C. Trombone positions use the basic open-tube B-flat chart, without alternate positions or intonation offsets. The player emits fixed-tempo synthesized tones while preserving entered durations/rests/ties and supported repeat regions. It does not reproduce dynamics, articulation, fermata stretching, expressive tempo, or recording alignment.
