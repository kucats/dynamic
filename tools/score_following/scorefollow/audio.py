"""Causal baseline acoustics: FFT-accelerated YIN, RMS and debounced articulation.

128 ms trailing window, 20 ms hop at 16 kHz. Designed for one dominant pitched
instrument, not source separation. The backend interface can be replaced later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from scipy.fft import irfft, rfft

SAMPLE_RATE = 16_000
HOP = 320
WINDOW = 2048


@dataclass(frozen=True)
class Observation:
    time: float
    pitch: float | None
    clarity: float
    rms: float
    onset: bool = False


class AcousticBackend(Protocol):
    def push(self, samples: np.ndarray, start_sample: int) -> list[Observation]: ...
    def reset(self) -> None: ...


def yin_pitch(x: np.ndarray, a4_hz: float = 440) -> tuple[float | None, float]:
    """Return fractional MIDI pitch and periodicity, not a calibrated probability."""
    x = np.asarray(x, dtype=np.float64)
    x = x - x.mean()
    if np.mean(x * x) < 1e-7:
        return None, 0.0
    # Exact difference on overlapping windows via autocorrelation and cumulative energy.
    n = len(x)
    corr = irfft(np.abs(rfft(x, 2 * n)) ** 2, 2 * n)[:n]
    energy = np.concatenate(([0.0], np.cumsum(x * x)))
    tau_max = min(int(SAMPLE_RATE / 40), n // 2)
    lag = np.arange(1, tau_max + 1)
    diff = np.maximum(0, energy[n - lag] + energy[n] - energy[lag] - 2 * corr[lag])
    cmnd = diff * lag / np.maximum(np.cumsum(diff), 1e-12)
    lo = max(2, int(SAMPLE_RATE / 1800))
    candidates = np.flatnonzero(cmnd[lo - 1 :] < 0.18) + lo
    if len(candidates):
        tau = int(candidates[0])
        while tau < tau_max and cmnd[tau] < cmnd[tau - 1]:
            tau += 1
    else:
        tau = int(np.argmin(cmnd[lo - 1 :]) + lo)
    clarity = float(np.clip(1 - cmnd[tau - 1], 0, 1))
    if clarity < 0.70:
        return None, clarity
    refined = float(tau)
    if 1 < tau < tau_max:
        a, b, c = cmnd[tau - 2 : tau + 1]
        denom = a - 2 * b + c
        if abs(denom) > 1e-12:
            refined += float(np.clip(0.5 * (a - c) / denom, -0.5, 0.5))
    hz = SAMPLE_RATE / refined
    midi = 69 + 12 * np.log2(hz / a4_hz)
    return (float(midi), clarity) if 12 <= midi <= 120 else (None, 0.0)


class StreamingAudio:
    def __init__(self, a4_hz: float = 440):
        self.a4_hz = a4_hz
        self.reset()

    def reset(self):
        self.buffer = np.empty(0, dtype=np.float32)
        self.window = np.zeros(WINDOW, dtype=np.float32)
        self.cursor: int | None = None
        self.pitch: float | None = None
        self.pending: int | None = None
        self.pending_count = 0
        self.silent_hops = 3
        self.previous_rms = 0.0
        self.last_onset = -100.0
        # A short amplitude notch is a useful articulation cue when the player
        # repeats the same pitch. Keep it separate from the stable pitch anchor:
        # the 128 ms YIN window intentionally lags note boundaries.
        self.dip_rms: float | None = None
        self.dip_time: float | None = None
        self.dip_pitch: float | None = None

    def push(self, samples: np.ndarray, start_sample: int) -> list[Observation]:
        if self.cursor is None:
            self.cursor = start_sample
        elif self.cursor + len(self.buffer) != start_sample:
            self.reset()
            self.cursor = start_sample
        self.buffer = np.concatenate((self.buffer, np.asarray(samples, dtype=np.float32)))
        result = []
        while len(self.buffer) >= HOP:
            hop, self.buffer = self.buffer[:HOP], self.buffer[HOP:]
            self.window[:-HOP] = self.window[HOP:]
            self.window[-HOP:] = hop
            self.cursor += HOP
            t = self.cursor / SAMPLE_RATE
            rms = float(np.sqrt(np.mean(hop * hop)))
            pitch, clarity = yin_pitch(self.window, self.a4_hz) if rms >= 0.003 else (None, 0.0)
            onset = False
            # Track a pronounced hop-energy dip. For a same-pitch reattack we
            # wait 120 ms before committing, because YIN can still report the
            # previous pitch for ~100 ms after an actual pitch change.
            if self.pitch is not None and self.previous_rms > 0.02 and rms < self.previous_rms * 0.72:
                self.dip_rms = rms
                self.dip_time = t
                self.dip_pitch = self.pitch
            if pitch is None:
                self.silent_hops += 1
                self.pending = None
                self.pending_count = 0
                if self.silent_hops >= 3:
                    self.pitch = None
                    self.dip_rms = self.dip_time = self.dip_pitch = None
                elif self.dip_time is not None and t - self.dip_time > 0.30:
                    self.dip_rms = self.dip_time = self.dip_pitch = None
            else:
                rounded = round(pitch)
                self.pending_count = self.pending_count + 1 if self.pending == rounded else 1
                self.pending = rounded
                change = self.pitch is None or abs(pitch - self.pitch) > 0.75

                # If the delayed pitch estimate has clearly moved away from the
                # pre-dip note, this was a pitch change rather than a reattack.
                if self.dip_pitch is not None and abs(pitch - self.dip_pitch) > 0.75:
                    self.dip_rms = self.dip_time = self.dip_pitch = None
                dip_reattack = False
                if self.dip_time is not None and self.dip_pitch is not None:
                    age = t - self.dip_time
                    dip_reattack = (
                        0.12 <= age <= 0.30
                        and abs(pitch - self.dip_pitch) <= 0.5
                        and rms > max(0.01, self.dip_rms * 1.25)
                    )

                reattack = self.silent_hops >= 2 or dip_reattack or (
                    rms > max(0.01, self.previous_rms * 2.8) and t - self.last_onset > 0.12
                )
                # Four equal rounded-pitch observations reject the short
                # intermediate pitches produced as the trailing YIN window
                # crosses a boundary (for example 60 -> 61 -> 62). Very large
                # jumps receive two extra hops because octave/transient errors
                # are especially common there.
                required = 6 if self.pitch is not None and abs(pitch - self.pitch) > 19 else 4
                if (change and self.pending_count >= required) or (reattack and not change):
                    onset = t - self.last_onset >= 0.08
                    if onset:
                        self.pitch = pitch
                        self.last_onset = t
                        self.dip_rms = self.dip_time = self.dip_pitch = None

                # Deliberately do not chase every fractional YIN estimate here.
                # self.pitch is the last articulated-note anchor; updating it
                # every 20 ms makes semitone steps disappear into a slow glide.
                self.silent_hops = 0
            self.previous_rms = rms
            result.append(Observation(t, pitch, clarity, rms, onset))
        return result
