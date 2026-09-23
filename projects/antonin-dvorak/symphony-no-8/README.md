# Dvořák: Symphony No. 8, Op. 88

This work directory keeps trombone-specific transcription code and note data together. The public HTML pages and annotated PDFs live under `public/composers/antonin-dvorak/symphony-no-8/`.

## Included readings

- **Trombone I, movement IV:** 263 detected played noteheads from source pages 3–5. The PDF shows concert pitch and a primary slide position; one note is marked for review. Other labels are still score-derived candidates.
- **Trombone II:** 540 playable noteheads visually checked across movements I and IV. Movements II and III are tacet; 95 cue detections are not included in the checked playable-note count.
- **Trombone III:** 494 detected noteheads from source pages 10–13; 103 are amber and need voice or cue confirmation. The rehearsal-C anchor is D3–G3–E3, positions 4–4–2.

All octave numbers use C4 = middle C; H is B natural. Slide positions are conventional starting choices for B-flat trombone, and are not an intonation guarantee. None of the guides is aligned to a performance recording.

## Reproduction inputs and boundaries

The source score PDF and its Audiveris 5.11.0 OMR project are identified by SHA-256 in `public/catalog.json` and the note JSON. Those inputs, rendered source-page images, and audio are not included. Re-running extraction requires the matching local score and OMR project; the OMR IDs and part-specific system filters are tied to the recorded OMR hash. Do not substitute another recognition project without rechecking the corrections.

The Trombone I and III `transcribe.py` scripts export note JSON/CSV from that exact OMR project. The per-part `render.py` scripts create annotated PDFs from the note JSON and rendered source-page images. To rerender, pass the data, image directory, output directory, and local font file(s) explicitly. Pillow and ReportLab are required; the included scripts do not embed system font paths.

Example Trombone I extraction:

```sh
python3 projects/antonin-dvorak/symphony-no-8/trombone-i-movement-iv/transcribe.py \
  --omr local-inputs/source-recognition.omr \
  --source-sha 6c161bf1a3a10e54194fecec8b52e2bc6a6fa0de7638c21296808e5456719d8c \
  --json build/tb1-notes.json --csv build/tb1-notes.csv
```

Example PDF rerender:

```sh
python3 projects/antonin-dvorak/symphony-no-8/trombone-i-movement-iv/render.py \
  --data build/tb1-notes.json --images local-inputs/source-pages \
  --output build/tb1-reading --font-regular local-fonts/regular.ttf \
  --font-bold local-fonts/bold.ttf
```

Trombone III uses the same flags and has a regression assertion for the rehearsal-C pitches and positions. Trombone II rendering accepts `--data`, `--images`, `--output`, and `--font`; its checked transcription JSON/CSV is provided directly because the publication bundle does not include the source OMR project.

## Review status

The catalog distinguishes the visually checked Trombone II transcription from the provisional Trombone I and III candidates. A `reviewed` score reading means the printed playable noteheads were visually checked; it does not mean the part was checked against a recording or independently approved by a performer.
