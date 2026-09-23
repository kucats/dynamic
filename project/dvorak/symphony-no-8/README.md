# Dvořák Symphony No. 8 score-reading files

The score-reading material is separated by instrument part. Trombone pitch data uses concert pitch (C4 = middle C, H = B-natural, Bb = B-flat) and standard open-tube B-flat trombone positions. Corno II is read at printed written pitch in F-horn notation, with concert pitch shown a perfect fifth lower.

## Trombone II processing record

The prior Trombone II run processed four source pages and records 540 played noteheads, 310 rest events, and 16 ties. Its receipt measured **70.3 minutes wall time** from preparation through OMR experiments, source review, rhythm transcription, PDF/player implementation, and QA; this is elapsed session time, not pure CPU or focused labor. Four-page OMR processing took 193.56 seconds, and a cached rebuild took 2.614 seconds with identical note JSON. The browser/offline-audio QA checked 540 unique IDs, zero missing durations, contiguous movement I/IV timelines with repeat policies, pitch frequencies, rest/tie windows, and that the active highlight left the printed notehead visible. The test did not constitute independent musician listening or synchronization to the linked recording.

## Current limits

Trombone I movement I has 282 note pitches but no rhythm transcription; movement IV has 261 events whose timing data is marked provisional. Trombone III movement IV is explicitly marked a trial reading, with 38 low-confidence or unusual candidates and three unassigned positions. Nabucco Trombone II pages 2–4 remain an OMR candidate draft with 455 candidates and no verified-note count. These limitations appear in the per-part project records and catalog.

Horn II has its own source-bound independent audits in `horn-ii/`. The previous movement I/III player exports are archived as superseded because the independent audit found notehead-role and clef discrepancies. Full movement playback is disabled across Horn II until corrected complete note and rhythm readings pass an independent audit.
