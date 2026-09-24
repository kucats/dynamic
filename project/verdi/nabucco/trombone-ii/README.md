# Nabucco / Sinfonia / Trombone II

The supplied score identifies this as TROMBONE 2. The source PDF has 34 pages; this repository records its SHA-256 and publishes only derivatives from physical pages 2–4. The source PDF and raw page scans are not committed.

## Pitch-checked excerpt

The catalog PDF at `public/composers/giuseppe-verdi/nabucco-sinfonia/trombone-ii-p2-4-checked/` covers 401 visible noteheads across 38 systems: 124 on source page 2, 125 on page 3, and 152 on page 4. Three page-level model reviews checked printed bass-clef pitch, spelling, octave, key signatures and accidentals, conventional basic slide position, and label coverage. The audit receipt is `reading-audit.json`.

The excerpt's exploratory player requires acknowledgement before note audition or playback. Durations, rests, ties, repeats, cues, meter, tempo, and recording synchronization were not audited. The warning does not validate the timing. Slide positions are conventional starting choices and may vary by instrument and player.

The matching 34-page part is listed in the Ricordi/Kalmus set as Public Domain on IMSLP, but the supplied PDF was not byte-compared with that file. See the [IMSLP work page](https://imslp.org/wiki/Nabucco_(Verdi,_Giuseppe)) for that edition listing.

## DYNAMIC reader transcription

`dynamic/part.json` and `dynamic/pages/` contain a separate 492-event page-by-page transcription for the same source pages. Its DYNAMIC reader and A3 PDF are generated in `public/reader/`. This transcription has not received an independent musician audit. The E-sharp at source page 2, bar 4 may be E-natural; it remains flagged and excluded from click audition, long-tone practice, and continuous playback. Tempo values without printed metronome marks are estimates; fermatas and ritardando are not modeled. The part data and generated reader JSON retain the full limitations.

The 401 visible noteheads in the pitch-checked PDF and the 492 events in the DYNAMIC reader are counts from distinct artifacts and methods. The 401-note pitch audit does not validate or reconcile the DYNAMIC event list or its timing.

## Earlier candidate artifacts

The composer catalog also retains older readings, an overview, and a Fuyomi candidate viewer. They remain marked draft: page 2 system 11's meter/key context is unclear, key-signature counts on pages 3–4 remain unresolved in those artifacts, and the 455 OMR candidate count differs from the MusicXML count by six. Their structural checks are not a complete independent note audit.

## Outputs and reproducibility

- Pitch-checked derivative PDF: `public/composers/giuseppe-verdi/nabucco-sinfonia/trombone-ii-p2-4-checked/Nabucco_Sinfonia_Trombone_II_source_pages_2-4_pitch_checked.pdf`
- Its exploratory player: `public/composers/giuseppe-verdi/nabucco-sinfonia/trombone-ii-p2-4-checked/exploratory-playback.html`
- DYNAMIC page data: `dynamic/`
- DYNAMIC build guidance: `tools/dynamic/RUNBOOK.md`
- DYNAMIC page-reading prompt: `tools/dynamic/prompts/21_nabucco_trombone_page.md`
