"""Bounded event-level beam alignment with pitch/rhythm likelihood and restart seeds.

This is a new experimental baseline, NOT an implementation or reproduction of a
particular published HMM. Confidence is a heuristic candidate-separation score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .audio import Observation
from .schema import Options, Score


@dataclass(frozen=True)
class Hypothesis:
    index: int
    tempo: float
    last_time: float
    log_weight: float
    evidence: int


def pitch_cost(actual: float, expected: float) -> float:
    distance = abs(actual - expected)
    # Octave confusions are less bad than unrelated notes, but never free.
    octave = abs(distance - 12)
    return min(9.0, (distance / 0.65) ** 2 / 2, 2.8 + (octave / 0.7) ** 2 / 2)


class Follower:
    def __init__(self, score: Score, options: Options | None = None):
        self.score = score
        self.score_digest = score.digest
        self.options = options or Options()
        self.notes = [e for e in score.events if e.pitch is not None]
        self.pitches = [score.concert_pitch(e) for e in self.notes]
        self.reset(self.options.start_event_id)

    def reset(self, event_id: str | None = None):
        self.beam: list[Hypothesis] = []
        self.hint = next((i for i, n in enumerate(self.notes) if n.event_id == event_id), None)
        self.last_time = 0.0
        self.last_voiced = -100.0
        self.last_observation: Observation | None = None
        self.confidence = 0.0
        self.match_quality = 0.0
        self.observations = 0
        self.gaps = 0
        self.paused = False
        self.status = "acquiring"
        self.last_reported_index: int | None = None
        self.jumps = 0

    def discontinuity(self):
        # No fictional silence or tempo extrapolation across lost audio.
        self.beam = []
        self.confidence = 0.0
        self.status = "lost"
        self.gaps += 1
        self.hint = None

    def consume(self, obs: Observation) -> dict:
        if obs.time <= self.last_time:
            raise ValueError("observations must have strictly increasing audio timestamps")
        self.last_time = obs.time
        self.last_observation = obs
        if self.paused:
            return self.snapshot()
        if obs.pitch is not None and obs.clarity >= 0.70:
            self.last_voiced = obs.time
            if obs.onset:
                self._align(obs)
        return self.snapshot()

    def _align(self, obs: Observation):
        candidates: dict[int, Hypothesis] = {}
        self.observations += 1
        actual = float(obs.pitch)

        def add(h: Hypothesis):
            current = candidates.get(h.index)
            if current is None or h.log_weight > current.log_weight:
                candidates[h.index] = h

        for h in self.beam:
            # Insertion: tolerate a wrong extra note, keeping last matched onset time.
            add(Hypothesis(h.index, h.tempo, h.last_time, h.log_weight - 4.5, h.evidence))
            for step in (1, 2, 3):
                j = h.index + step
                if j >= len(self.notes):
                    continue
                dq = self.notes[j].start - self.notes[h.index].start
                dt = obs.time - h.last_time
                if dq <= 0 or dt <= 0:
                    continue
                expected_dt = dq * 60 / h.tempo
                log_ratio = abs(math.log(max(dt, 0.01) / expected_dt))
                # Robust, capped rhythm penalty allows fermata / tempo change.
                timing = min(2.2, log_ratio * 1.2)
                cost = pitch_cost(actual, self.pitches[j])
                weight = h.log_weight - cost - timing - (step - 1) * 2.0
                measured_tempo = dq * 60 / dt
                tempo = h.tempo
                if cost < 1.5 and 20 <= measured_tempo <= 300:
                    tempo = 0.7 * tempo + 0.3 * measured_tempo
                evidence = min(12, h.evidence + 1) if cost < 1.5 else max(0, h.evidence - 1)
                add(Hypothesis(j, tempo, obs.time, weight, evidence))

        # Global acquisition/restart seeds compete only after several coherent notes.
        # Matching all notes is bounded by the 4096-event score contract.
        base = max((h.log_weight for h in self.beam), default=0)
        for j, expected in enumerate(self.pitches):
            cost = pitch_cost(actual, expected)
            if cost > 2.5:
                continue
            prior = -7.0 if self.beam else 0.0
            if not self.beam and self.hint is not None:
                prior -= min(8, abs(j - self.hint) * 1.5)
            add(Hypothesis(j, self.score.tempo_bpm, obs.time, base + prior - cost, 1))
        if not candidates:
            self.confidence = 0.0
            self.status = "lost"
            return
        ranked = sorted(candidates.values(), key=lambda h: (-h.log_weight, h.index))
        best = ranked[0]
        top = ranked[: self.options.beam_width]
        self.beam = [
            Hypothesis(h.index, h.tempo, h.last_time, h.log_weight - best.log_weight, h.evidence) for h in top
        ]
        margin = best.log_weight - ranked[1].log_weight if len(ranked) > 1 else 5.0
        self.match_quality = math.exp(-pitch_cost(actual, self.pitches[best.index]))
        self.confidence = float(
            (1 - math.exp(-max(0, margin))) * min(1, best.evidence / 3) * self.match_quality
        )
        self.status = "tracking" if self.confidence >= 0.55 and best.evidence >= 3 else "uncertain"
        if self.last_reported_index is not None and self.status == "tracking":
            if best.index < self.last_reported_index or best.index > self.last_reported_index + 3:
                self.jumps += 1
        if self.status == "tracking":
            self.last_reported_index = best.index
        self.hint = None

    def snapshot(self) -> dict:
        status = self.status
        silent = self.last_time - self.last_voiced
        confidence = self.confidence
        if self.paused:
            status, confidence = "paused", 0.0
        elif silent > self.options.silence_hold_s and self.beam:
            status, confidence = "holding", 0.0
        position = None
        alternatives = []
        if self.beam:
            best = self.beam[0]
            n = self.notes[best.index]
            phase = min(n.duration, max(0, (self.last_time - best.last_time) * best.tempo / 60))
            position = {
                "event_id": n.event_id,
                "source_id": n.source_id or n.event_id,
                "occurrence": n.occurrence,
                "measure": n.measure,
                "beat": n.beat,
                "page": n.page,
                "anchor": n.anchor,
                "note_index": best.index,
                "score_quarter": n.start,
                "predicted_quarter": n.start + phase,
                "tempo_bpm": round(best.tempo, 2),
                "confirmed": status == "tracking",
            }
            for h in self.beam[:5]:
                alternatives.append(
                    {
                        "event_id": self.notes[h.index].event_id,
                        "relative_log_weight": round(h.log_weight, 4),
                        "evidence_notes": h.evidence,
                    }
                )
        obs = self.last_observation
        return {
            "type": "position",
            "algorithm": "monophonic-beam-v1",
            "audio_time_s": round(self.last_time, 5),
            "status": status,
            "confidence": round(confidence, 4),
            "confidence_kind": "uncalibrated_heuristic",
            "position": position,
            "alternatives": alternatives,
            "pitch_midi": round(obs.pitch, 3) if obs and obs.pitch is not None else None,
            "rms": round(obs.rms, 6) if obs else 0.0,
            "onset_count": self.observations,
            "gap_count": self.gaps,
            "jump_count": self.jumps,
            "score_sha256": self.score_digest,
            "score_audit_status": self.score.audit_status,
        }
