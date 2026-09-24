"""Experimental ensemble reference follower: spectral chroma + bounded subsequence DTW.

This produces reference-audio seconds, NOT score beats, trombone notes or ground truth.
Frames use only a trailing 256ms window. Online acquisition uses the past 20 seconds;
offline matching is explicitly a separate operation allowed to see a whole excerpt.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from .audio import SAMPLE_RATE

WINDOW = 4096
HOP = 1600
STEP = HOP / SAMPLE_RATE


@dataclass(frozen=True)
class ChromaFrame:
    time: float
    chroma: np.ndarray
    rms: float


class ChromaStream:
    """Power is combined across channels BEFORE folding; anti-phase audio cannot cancel."""

    def __init__(self):
        frequencies = np.fft.rfftfreq(WINDOW, 1 / SAMPLE_RATE)
        midi = 69 + 12 * np.log2(np.maximum(frequencies, 0.01) / 440)
        distance = (midi[None, :] - np.arange(12)[:, None] + 6) % 12 - 6
        self.weights = np.exp(-0.5 * (distance / 0.5) ** 2).astype(np.float32)
        self.weights[:, (frequencies < 55) | (frequencies > 4000)] = 0
        self.hann = np.hanning(WINDOW).astype(np.float32)
        self.reset()

    def reset(self):
        self.buffer = None
        self.cursor = None
        self.received = None

    def push(self, samples: np.ndarray, start_sample: int) -> list[ChromaFrame]:
        x = np.asarray(samples, dtype=np.float32)
        if x.ndim == 1:
            x = x[:, None]
        if x.ndim != 2 or x.shape[1] not in (1, 2) or not np.isfinite(x).all():
            raise ValueError("finite mono/stereo samples required")
        if not isinstance(start_sample, int) or start_sample < 0:
            raise ValueError("invalid sample clock")
        if self.received is not None and start_sample != self.received:
            raise ValueError("chroma input gap requires explicit reset")
        if self.buffer is None:
            self.buffer = np.empty((0, x.shape[1]), dtype=np.float32)
            self.cursor = start_sample
        if x.shape[1] != self.buffer.shape[1]:
            raise ValueError("channel count changed")
        self.received = start_sample + len(x)
        self.buffer = np.concatenate((self.buffer, x))
        rows = []
        while len(self.buffer) >= WINDOW:
            window = self.buffer[:WINDOW]
            spectrum = np.abs(np.fft.rfft(window * self.hann[:, None], axis=0)) ** 2
            power = spectrum.mean(axis=1)
            chroma = np.sqrt(self.weights @ power)
            chroma = np.maximum(0, chroma - chroma.mean())
            chroma /= max(float(np.linalg.norm(chroma)), 1e-12)
            rows.append(
                ChromaFrame(
                    (self.cursor + WINDOW) / SAMPLE_RATE,
                    chroma.astype(np.float32),
                    float(np.sqrt(np.mean(window**2))),
                )
            )
            self.buffer = self.buffer[HOP:]
            self.cursor += HOP
        return rows


def features(samples: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    stream = ChromaStream()
    rows = []
    for start in range(0, len(samples), SAMPLE_RATE):
        rows.extend(stream.push(samples[start : start + SAMPLE_RATE], start))
    if not rows:
        raise ValueError("recording shorter than 256ms")
    return (
        np.stack([r.chroma for r in rows]),
        np.array([r.time for r in rows]),
        np.array([r.rms for r in rows]),
    )


def _matrix(value: np.ndarray) -> np.ndarray:
    x = np.asarray(value, dtype=np.float32)
    if x.ndim != 2 or x.shape[1] != 12 or not 3 <= len(x) <= 12000 or not np.isfinite(x).all():
        raise ValueError("bounded finite frames x 12 chromagram required")
    norms = np.linalg.norm(x, axis=1)
    if np.any(x < 0) or np.any(norms > 1.001):
        raise ValueError("nonnegative L2-normalized chroma required")
    return x


def match_window(
    query: np.ndarray, reference: np.ndarray, *, top_k: int = 3, predicted_end: float | None = None
) -> list[dict]:
    """Subsequence DTW with (1,1)/(1,2)/(2,1) steps. Linear row-memory, bounded pointers.

    Cost is normalized by twice query frame count, not a likelihood. The step pattern
    permits local speed ratios 0.5..2. No score labels enter feature extraction.
    """
    q, r = _matrix(query), _matrix(reference)
    if len(q) * len(r) > 36_000_000 or not 1 <= top_k <= 8:
        raise ValueError("alignment budget exceeded")
    if len(q) > 2 * len(r):
        raise ValueError("reference too short for the permitted DTW step ratios")
    cost = np.maximum(0, 1 - q @ r.T)
    n, m = cost.shape
    prev2 = np.full(m + 1, np.inf)
    prev = np.zeros(m + 1)
    pointer = np.zeros((n, m), dtype=np.uint8)
    for i in range(n):
        a = prev[:-1] + 2 * cost[i]
        b = np.full(m, np.inf)
        b[1:] = prev[:-2] + cost[i, :-1] + cost[i, 1:]
        c = prev2[:-1] + cost[i - 1] + cost[i] if i >= 1 else np.full(m, np.inf)
        best = np.minimum(a, np.minimum(b, c))
        pointer[i] = np.where(a <= np.minimum(b, c), 1, np.where(b <= c, 2, 3))
        prev2, prev = prev, np.r_[np.inf, best]
    rank = prev[1:] / (2 * n)
    choices = []
    if predicted_end is not None:
        center = round((predicted_end - WINDOW / SAMPLE_RATE) / STEP)
        lo, hi = max(0, center - 30), min(m, center + 31)
        if lo < hi:
            choices.append(lo + int(np.argmin(rank[lo:hi])))
    remaining = rank.copy()
    for _ in range(top_k):
        j = int(np.argmin(remaining))
        if not np.isfinite(remaining[j]):
            break
        if j not in choices:
            choices.append(j)
        remaining[max(0, j - 30) : min(m, j + 31)] = np.inf
    result = []
    for end in choices:
        i, j, path = n - 1, end, []
        while i >= 0 and j >= 0:
            path.append((i, j))
            p = pointer[i, j]
            i, j = (i - 1, j - 1) if p == 1 else ((i - 1, j - 2) if p == 2 else (i - 2, j - 1))
        path.reverse()
        result.append(
            {
                "cost": float(rank[end]),
                "reference_start_s": path[0][1] * STEP + WINDOW / SAMPLE_RATE,
                "reference_end_s": end * STEP + WINDOW / SAMPLE_RATE,
                "path_frames": path,
            }
        )
    return sorted(result, key=lambda item: item["cost"])


class ReferenceTracker:
    """Causal rolling-window candidate tracker. No automatic score-page command output."""

    def __init__(self, reference: np.ndarray, *, window_frames: int = 200, update_frames: int = 10):
        self.reference = _matrix(reference)
        if not 40 <= window_frames <= 200 or not 1 <= update_frames <= 20:
            raise ValueError("invalid tracker window/cadence")
        if len(self.reference) * 2 < window_frames:
            raise ValueError("reference too short for acquisition window")
        self.window_frames, self.update_frames = window_frames, update_frames
        self.reset()

    def reset(self):
        self.frames = deque(maxlen=self.window_frames)
        self.count, self.continuity = 0, 0
        self.last_time = None
        self.last_candidate = None
        self.locked = False
        self.bad_updates = 0

    def consume(self, frame: ChromaFrame) -> dict | None:
        if self.last_time is not None and not 0.099 <= frame.time - self.last_time <= 0.101:
            raise ValueError("reference tracker requires continuous 100ms frames; reset on gap")
        self.last_time = frame.time
        self.frames.append(frame)
        self.count += 1
        if len(self.frames) < self.window_frames or self.count % self.update_frames:
            return None
        q = np.stack([f.chroma for f in self.frames])
        silence = all(f.rms < 0.002 for f in list(self.frames)[-4:])
        diversity = float(np.mean(np.linalg.norm(q - q.mean(axis=0), axis=1)))
        prediction = None
        if self.last_candidate and self.locked:
            prediction = self.last_candidate["reference_end_s"] + self.update_frames * STEP
        matches = match_window(q, self.reference, top_k=3, predicted_end=prediction)
        global_best = matches[0]
        best = global_best
        if prediction is not None:
            local = [m for m in matches if abs(m["reference_end_s"] - prediction) <= 3.1]
            if local:
                candidate = min(local, key=lambda m: m["cost"])
                if candidate["cost"] < 0.30 and candidate["cost"] <= global_best["cost"] + 0.06:
                    best = candidate
        alternatives = [m for m in matches if abs(m["reference_end_s"] - best["reference_end_s"]) > 3]
        margin = min((m["cost"] - best["cost"] for m in alternatives), default=0)
        advance = (
            best["reference_end_s"] - self.last_candidate["reference_end_s"] if self.last_candidate else None
        )
        consistent = (
            advance is not None
            and 0.4 * self.update_frames * STEP <= advance <= 2.1 * self.update_frames * STEP
        )
        supported = not silence and diversity > 0.20 and best["cost"] < 0.30
        strong = supported and (
            (best["cost"] < 0.26 and margin > 0.035) or (best["cost"] < 0.06 and margin > 0.01)
        )
        self.continuity = (
            self.continuity + 1 if consistent and (strong or self.locked) else (1 if strong else 0)
        )
        if not self.locked and self.continuity >= 3:
            self.locked = True
        if self.locked and (not supported or not consistent):
            self.bad_updates += 1
        else:
            self.bad_updates = 0
        if self.bad_updates >= 3 or silence:
            self.locked = False
            self.continuity = 0
        stable = supported and self.locked and consistent
        self.last_candidate = best if supported else None
        if not supported:
            self.continuity = 0
        return {
            "type": "reference_position",
            "algorithm": "ensemble-chroma-subsequence-v1",
            "audio_time_s": frame.time,
            "reference_time_s": best["reference_end_s"],
            "status": "holding" if silence else ("tracking_candidate" if stable else "uncertain"),
            "cost": best["cost"],
            "alternative_margin": float(margin),
            "diversity": diversity,
            "context_s": self.window_frames * STEP,
            "continuity_updates": self.continuity,
            "score_position": None,
            "confirmed": False,
            "evidence_kind": "reference_audio_alignment_not_ground_truth",
            "alternatives": [{k: v for k, v in m.items() if k != "path_frames"} for m in matches],
        }
