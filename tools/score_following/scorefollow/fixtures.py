"""Original synthetic fixtures. No commercial score or private recording is included."""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

from .schema import Note, Score


def demo_score() -> Score:
    pitches = [48, 50, 55, 52, 57, 53, 53, 60, 55, 58, 50, 54, 59, 52, 56, 48]
    events = []
    for i, pitch in enumerate(pitches):
        events.append(
            Note(
                event_id=f"n{i:03}",
                source_id=f"demo-note-{i}",
                measure=str(i // 4 + 1),
                beat=i % 4 + 1,
                start=float(i),
                duration=0.8,
                pitch=pitch,
                anchor=f"demo-{i}",
            )
        )
        events.append(
            Note(event_id=f"r{i:03}", measure=str(i // 4 + 1), beat=i % 4 + 1.8, start=i + 0.8, duration=0.2)
        )
    return Score(
        title="DYNAMIC original test phrase",
        part="Synthetic solo",
        audit_status="synthetic",
        provenance="Procedurally generated original fixture, seed 20260924",
        tempo_bpm=120,
        events=events,
    )


def synthesize(
    score: Score,
    *,
    order: list[int] | None = None,
    tempo_scale: float = 1,
    noise: float = 0,
    cents: float = 0,
    seed: int = 20260924,
    sample_rate: int = 16000,
    wrong: dict[int, float] | None = None,
    pauses: dict[int, float] | None = None,
) -> tuple[np.ndarray, list[dict]]:
    notes = [n for n in score.events if n.pitch is not None]
    order = order if order is not None else list(range(len(notes)))
    rng = np.random.default_rng(seed)
    chunks = [np.zeros(int(sample_rate * 0.24), dtype=np.float32)]
    labels = []
    clock = len(chunks[0]) / sample_rate
    for k, idx in enumerate(order):
        n = notes[idx]
        pause = (pauses or {}).get(k, 0)
        if pause:
            chunks.append(np.zeros(round(pause * sample_rate), dtype=np.float32))
            clock += len(chunks[-1]) / sample_rate
        q = notes[idx + 1].start - n.start if idx + 1 < len(notes) else n.duration + 0.2
        duration = n.duration * 60 / score.tempo_bpm / tempo_scale
        interval = max(duration, q * 60 / score.tempo_bpm / tempo_scale)
        count = round(interval * sample_rate)
        tone_count = min(count, round(duration * sample_rate))
        t = np.arange(tone_count) / sample_rate
        midi = (wrong or {}).get(k, score.concert_pitch(n)) + cents / 100
        # Fundamental and brass-like harmonics, finite attack/release, weak vibrato.
        phase = 2 * np.pi * (440 * 2 ** ((midi - 69) / 12)) * t + 0.025 * np.sin(2 * np.pi * 5 * t)
        signal = 0.23 * (np.sin(phase) + 0.32 * np.sin(2 * phase) + 0.12 * np.sin(3 * phase))
        envelope = np.minimum(1, t / 0.008) * np.minimum(1, (duration - t) / 0.02)
        chunk = np.zeros(count, dtype=np.float32)
        chunk[:tone_count] = signal * envelope
        chunk += rng.normal(0, noise, count).astype(np.float32)
        chunks.append(chunk)
        labels.append(
            {
                "onset_s": round(clock, 6),
                "offset_s": round(clock + duration, 6),
                "event_id": n.event_id,
                "note_index": idx,
                "midi": midi,
            }
        )
        clock += count / sample_rate
    chunks.append(np.zeros(round(sample_rate * 0.8), dtype=np.float32))
    return np.concatenate(chunks), labels


def write_fixture(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    score = demo_score()
    (directory / "score.json").write_text(score.model_dump_json(indent=2) + "\n")
    audio, labels = synthesize(score)
    with wave.open(str(directory / "performance.wav"), "wb") as w:
        w.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
    (directory / "labels.json").write_text(json.dumps(labels, indent=2) + "\n")
