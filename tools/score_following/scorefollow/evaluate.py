"""Offline replay and ground-truth scoring. Labels never enter the inference path."""

from __future__ import annotations

import json
import platform
import time
import wave
from pathlib import Path

import numpy as np

from .audio import HOP, SAMPLE_RATE, StreamingAudio
from .fixtures import demo_score, synthesize
from .follower import Follower
from .schema import Options, Score


def read_wav(path: Path) -> np.ndarray:
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("WAV exceeds 64 MiB; evaluate shorter excerpts")
    with wave.open(str(path), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getcomptype()) != (
            1,
            2,
            SAMPLE_RATE,
            "NONE",
        ):
            raise ValueError("WAV must be uncompressed mono PCM16 at 16000 Hz")
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768


def replay_array(score: Score, audio: np.ndarray, options: Options | None = None) -> tuple[list[dict], dict]:
    if audio.ndim != 1 or len(audio) == 0 or not np.isfinite(audio).all():
        raise ValueError("audio must be a nonempty finite mono array")
    options = options or Options()
    if score.audit_status == "unreviewed" and not options.allow_unreviewed:
        raise ValueError("unreviewed score requires --allow-unreviewed")
    dsp, follower = StreamingAudio(options.a4_hz), Follower(score, options)
    rows, durations = [], []
    started = time.perf_counter()
    for start in range(0, len(audio), HOP):
        t = time.perf_counter()
        for obs in dsp.push(audio[start : start + HOP], start):
            rows.append(follower.consume(obs))
        durations.append((time.perf_counter() - t) * 1000)
    elapsed = time.perf_counter() - started
    metrics = {
        "audio_seconds": len(audio) / SAMPLE_RATE,
        "compute_seconds": elapsed,
        "real_time_factor": elapsed / max(len(audio) / SAMPLE_RATE, 1e-6),
        "hop_compute_p50_ms": float(np.percentile(durations, 50)),
        "hop_compute_p95_ms": float(np.percentile(durations, 95)),
        "hop_compute_p99_ms": float(np.percentile(durations, 99)),
        "frames": len(rows),
        "score_sha256": score.digest,
        "latency_note": "Compute only, not microphone-to-screen/network latency",
    }
    return rows, metrics


def grade(rows: list[dict], labels: list[dict]) -> dict:
    """Report both all-frame accuracy and post-attack accuracy; abstentions count as misses.

    Note evaluation includes every pitched ground-truth interval [onset, offset).
    Post-attack frames exclude its first 200ms (no oracle trimming in inference).
    'confirmed_precision' denominator is only confirmed frames; coverage also reported.
    """
    if not isinstance(labels, list) or len(labels) > 100_000:
        raise ValueError("labels must be a bounded array")
    previous = -1.0
    for label in labels:
        if not (
            isinstance(label.get("event_id"), str)
            and np.isfinite(label["onset_s"])
            and np.isfinite(label["offset_s"])
            and 0 <= label["onset_s"] < label["offset_s"]
            and label["onset_s"] >= previous
        ):
            raise ValueError("invalid/non-monophonic labels")
        previous = label["offset_s"]
    counts = dict(
        frames=0, exact=0, post_attack_frames=0, post_attack_exact=0, confirmed=0, confirmed_correct=0
    )
    latencies = []
    for label in labels:
        match_times = []
        for r in rows:
            t = r["audio_time_s"]
            if not label["onset_s"] <= t < label["offset_s"]:
                continue
            counts["frames"] += 1
            p = r["position"]
            correct = bool(p and p["event_id"] == label["event_id"])
            counts["exact"] += correct
            if t >= label["onset_s"] + 0.2:
                counts["post_attack_frames"] += 1
                counts["post_attack_exact"] += correct
            if p and p["confirmed"]:
                counts["confirmed"] += 1
                counts["confirmed_correct"] += correct
            if correct:
                match_times.append(t - label["onset_s"])
        latencies.append(min(match_times) * 1000 if match_times else None)
    valid = [x for x in latencies if x is not None]
    return {
        **counts,
        "exact_frame_accuracy": counts["exact"] / max(1, counts["frames"]),
        "post_attack_200ms_accuracy": counts["post_attack_exact"] / max(1, counts["post_attack_frames"]),
        "confirmed_coverage": counts["confirmed"] / max(1, counts["frames"]),
        "confirmed_precision": counts["confirmed_correct"] / counts["confirmed"]
        if counts["confirmed"]
        else None,
        "detected_notes": len(valid),
        "total_notes": len(labels),
        "first_correct_p50_ms": float(np.median(valid)) if valid else None,
        "first_correct_p95_ms": float(np.percentile(valid, 95)) if valid else None,
        "per_note_first_correct_ms": latencies,
        "metric_note": "Synthetic/onset-to-first-correct estimate, not network/UI latency; onset transients included in all-frame accuracy",
    }


def benchmark(output: Path) -> list[dict]:
    output.mkdir(parents=True, exist_ok=True)
    score = demo_score()
    scenarios = {
        "clean": {},
        "noise": {"noise": 0.008},
        "tempo_slow": {"tempo_scale": 0.7},
        "tempo_fast": {"tempo_scale": 1.3},
        "detuned": {"cents": 28},
        "pause": {"pauses": {5: 2.0}},
        "restart": {"order": [0, 1, 2, 3, 4, 5, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 15]},
        "arbitrary_start": {"order": list(range(8, 16))},
    }
    results = []
    for name, kw in scenarios.items():
        audio, labels = synthesize(score, seed=91723, **kw)
        rows, timing = replay_array(score, audio)
        results.append({"scenario": name, **timing, **grade(rows, labels)})
        (output / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    record = {
        "algorithm": "monophonic-beam-v1",
        "test_data": "original synthetic, not real recordings",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "results": results,
    }
    (output / "benchmark.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    return results
