"""Offline/private recording analysis. This CLI never uploads media or fetches references."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from .audio import HOP, StreamingAudio
from .evaluate import grade, replay_array
from .recording import load_recording
from .reference import ChromaFrame, ReferenceTracker, features, match_window
from .schema import Options, Score


def diagnostic(recording) -> dict:
    result = recording.profile()
    result["channels_analysis"] = []
    pitches = []
    for mode in ["left", "right", "mix"] if recording.samples.shape[1] == 2 else ["mix"]:
        dsp, observations = StreamingAudio(), []
        x = recording.channel(mode)
        for start in range(0, len(x), HOP):
            observations.extend(dsp.push(x[start : start + HOP], start))
        pitch = np.array([o.pitch if o.pitch is not None else np.nan for o in observations])
        if mode != "mix":
            pitches.append(pitch)
        valid = np.isfinite(pitch)
        result["channels_analysis"].append(
            {
                "channel": mode,
                "voiced_fraction": float(valid.mean()),
                "onsets": sum(o.onset for o in observations),
                "midi_p05_p50_p95": np.percentile(pitch[valid], [5, 50, 95]).tolist()
                if valid.any()
                else None,
            }
        )
    if len(pitches) == 2:
        joint = np.isfinite(pitches[0]) & np.isfinite(pitches[1])
        result["jointly_voiced_fraction"] = float(joint.mean())
        result["stereo_pitch_agreement_within_half_semitone"] = (
            float(np.mean(np.abs(pitches[0][joint] - pitches[1][joint]) <= 0.5)) if joint.any() else None
        )
    result["note"] = "Voicing and stereo agreement do not identify an instrument or establish pitch accuracy."
    return result


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Private recording lab; no network or automatic score certification"
    )
    parser.add_argument("command", choices=("inspect", "compare", "follow", "evaluate"))
    parser.add_argument("recording", type=Path)
    parser.add_argument("--reference", type=Path, action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--score", type=Path)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--allow-unreviewed", action="store_true")
    parser.add_argument("--channel", choices=("mix", "left", "right"), default="mix")
    parser.add_argument("--timestamp-policy", choices=("strict", "samples"), default="strict")
    parser.add_argument("--reference-timestamp-policy", choices=("strict", "samples"), default="strict")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    recording = load_recording(args.recording, timestamp_policy=args.timestamp_policy)
    write_json(args.output / "profile.json", diagnostic(recording))
    if args.command == "inspect":
        return 0
    if args.command == "evaluate":
        if not args.score:
            parser.error("--score is required for evaluate")
        if args.score.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("score file exceeds size limit")
        score = Score.model_validate_json(args.score.read_bytes())
        trace, metrics = replay_array(
            score, recording.channel(args.channel), Options(allow_unreviewed=args.allow_unreviewed)
        )
        metrics.update(accuracy=None, alignment_status="unlabeled", source_sha256=recording.source_sha256)
        if args.labels:
            if args.labels.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("label file exceeds size limit")
            metrics["labeled_evaluation"] = grade(trace, json.loads(args.labels.read_text()))
            metrics["alignment_status"] = "evaluated_against_user_supplied_labels"
        with (args.output / "trace.jsonl").open("w") as handle:
            for row in trace:
                handle.write(json.dumps(row, allow_nan=False) + "\n")
        write_json(args.output / "metrics.json", metrics)
        return 0
    if not 1 <= len(args.reference) <= 8 or (args.command == "follow" and len(args.reference) != 1):
        parser.error("compare needs 1..8 references; follow needs exactly one")
    q, times, rms = features(recording.samples)
    results = []
    for index, path in enumerate(args.reference):
        reference = load_recording(path, timestamp_policy=args.reference_timestamp_policy)
        r, _, _ = features(reference.samples)
        if args.command == "compare":
            started = time.perf_counter()
            matches = match_window(q, r)
            # Use ordinal + hashes, not potentially private filenames or paths.
            results.append(
                {
                    "reference_index": index,
                    "reference_profile": reference.profile(),
                    "cost": matches[0]["cost"],
                    "reference_start_s": matches[0]["reference_start_s"],
                    "reference_end_s": matches[0]["reference_end_s"],
                    "compute_s": time.perf_counter() - started,
                }
            )
            write_json(
                args.output / f"path-{index}.json",
                {"query_frame_end_times": times.tolist(), "pairs": matches[0]["path_frames"]},
            )
        else:
            tracker = ReferenceTracker(r)
            with (args.output / "reference-trace.jsonl").open("w") as handle:
                for c, t, energy in zip(q, times, rms):
                    row = tracker.consume(ChromaFrame(float(t), c, float(energy)))
                    if row:
                        handle.write(json.dumps(row, allow_nan=False) + "\n")
            results.append(
                {
                    "reference_index": index,
                    "reference_profile": reference.profile(),
                    "mode": "causal_20s_lookback",
                    "score_position": None,
                }
            )
    write_json(
        args.output / "reference-results.json",
        {
            "results": results,
            "mode": "offline_full_excerpt" if args.command == "compare" else "causal",
            "source_sha256": recording.source_sha256,
            "accuracy": None,
            "score_position": None,
            "limitation": "Reference-audio candidates, not reviewed score/measure/trombone alignment. Mapping to a score requires separately reviewed anchors.",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
