"""Bounded local media ingestion. Never fetch URLs or export source metadata.

The decoder retains float headroom, original channel count and decoded audio time.
AAC float peaks above 1 are not proof that the source recording was clipped.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import av
import numpy as np

from .audio import SAMPLE_RATE

FORMATS = {".m4a": "mov", ".mp4": "mov", ".wav": "wav", ".flac": "flac", ".ogg": "ogg", ".mp3": "mp3"}


@dataclass(frozen=True)
class Recording:
    samples: np.ndarray  # frames x original channels, float32 at SAMPLE_RATE
    source_sha256: str
    source_rate: int
    codec: str
    origin_s: float | None
    timestamp_policy: str = "strict"
    timestamp_discontinuities: int = 0
    max_timestamp_deviation_s: float = 0.0

    def channel(self, mode: str = "mix") -> np.ndarray:
        if mode == "mix":
            return self.samples.mean(axis=1)
        index = {"left": 0, "right": 1}.get(mode)
        if index is None or index >= self.samples.shape[1]:
            raise ValueError("requested channel is unavailable")
        return self.samples[:, index]

    def profile(self) -> dict:
        x = self.samples.astype(np.float64)
        rms = np.sqrt(np.mean(x * x, axis=0))
        correlation = None
        if x.shape[1] == 2 and np.all(np.std(x, axis=0) > 1e-9):
            correlation = float(np.corrcoef(x.T)[0, 1])
        return {
            "source_sha256": self.source_sha256,
            "codec": self.codec,
            "source_rate": self.source_rate,
            "decoded_rate": SAMPLE_RATE,
            "channels": x.shape[1],
            "decoded_samples": len(x),
            "decoded_duration_s": len(x) / SAMPLE_RATE,
            "source_origin_s": self.origin_s,
            "peak_float": np.max(np.abs(x), axis=0).tolist(),
            "rms": rms.tolist(),
            "above_full_scale_fraction": np.mean(np.abs(x) > 1, axis=0).tolist(),
            "channel_correlation": correlation,
            "timestamp_policy": self.timestamp_policy,
            "timestamp_discontinuities": self.timestamp_discontinuities,
            "max_timestamp_deviation_s": self.max_timestamp_deviation_s,
            "headroom_note": "Float decoder overshoot is preserved, not proof of source clipping.",
            "alignment_status": "unlabeled",
            "accuracy": None,
        }


def load_recording(
    path: Path,
    *,
    max_seconds: float = 1200,
    max_bytes: int = 128 * 1024 * 1024,
    timestamp_policy: str = "strict",
) -> Recording:
    path = Path(path)
    if timestamp_policy not in ("strict", "samples"):
        raise ValueError("timestamp policy must be strict or samples")
    if not 0 < max_seconds <= 3600 or not 1 <= max_bytes <= 256 * 1024 * 1024:
        raise ValueError("invalid decode limits")
    fmt = FORMATS.get(path.suffix.lower())
    if fmt is None or not path.is_file() or path.is_symlink():
        raise ValueError("expected an existing local media file, not URL, playlist or symlink")
    if path.stat().st_size > max_bytes:
        raise ValueError("compressed input exceeds byte limit")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    chunks, count, origin, previous_end = [], 0, None, None
    discontinuities, max_deviation = 0, 0.0
    # Explicit demuxer + file-like input, no command shell or URL opening.
    with path.open("rb") as handle, av.open(handle, format=fmt, options={"enable_drefs": "0"}) as media:
        streams = list(media.streams.audio)
        if len(streams) != 1:
            raise ValueError("exactly one audio stream required")
        stream = streams[0]
        channels = stream.codec_context.channels
        rate = stream.codec_context.sample_rate
        if channels not in (1, 2) or not 8000 <= rate <= 192000:
            raise ValueError("supported input is mono/stereo, 8..192 kHz")
        codec = stream.codec_context.name
        resampler = av.AudioResampler(
            format="fltp", layout="mono" if channels == 1 else "stereo", rate=SAMPLE_RATE
        )

        def append(frame):
            nonlocal count, origin, previous_end, discontinuities, max_deviation
            x = frame.to_ndarray().T.astype(np.float32, copy=False)
            if x.ndim != 2 or x.shape[1] != channels or not np.isfinite(x).all():
                raise ValueError("invalid decoded PCM")
            stamp = float(frame.pts * frame.time_base) if frame.pts is not None and frame.time_base else None
            if stamp is not None:
                if origin is None:
                    origin = stamp
                if previous_end is not None and abs(stamp - previous_end) > 2 / SAMPLE_RATE:
                    discontinuities += 1
                    max_deviation = max(max_deviation, abs(stamp - previous_end))
                    if timestamp_policy == "strict":
                        raise ValueError(
                            "media timestamps are discontinuous; explicitly select sample-clock normalization to proceed"
                        )
                previous_end = stamp + len(x) / SAMPLE_RATE
            count += len(x)
            if count > round(max_seconds * SAMPLE_RATE):
                raise ValueError("decoded duration limit exceeded; no silent truncation")
            chunks.append(x.copy())

        for frame in media.decode(stream):
            if frame.samples > 1_000_000:
                raise ValueError("oversized decoder frame")
            for out in resampler.resample(frame):
                append(out)
        for out in resampler.resample(None):
            append(out)
    if not count:
        raise ValueError("empty recording")
    return Recording(
        np.concatenate(chunks),
        digest.hexdigest(),
        rate,
        codec,
        origin,
        timestamp_policy,
        discontinuities,
        max_deviation,
    )
