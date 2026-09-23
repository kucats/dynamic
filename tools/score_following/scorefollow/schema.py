"""Versioned, bounded score and wire contracts. Beats are quarter-note units."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Note(StrictModel):
    event_id: str = Field(min_length=1, max_length=100, pattern=r"^[\w.:-]+$")
    source_id: str | None = Field(default=None, max_length=100)
    occurrence: int = Field(default=1, ge=1, le=64)
    measure: str = Field(default="1", min_length=1, max_length=24)
    beat: float = Field(default=1, ge=0, le=256)
    start: float = Field(ge=0, le=100_000)
    duration: float = Field(gt=0, le=256)
    pitch: float | None = Field(default=None, ge=12, le=120)
    page: int | None = Field(default=None, ge=1, le=9999)
    # Opaque frontend anchor only. No server-side URL fetch or filesystem access.
    anchor: str | None = Field(default=None, max_length=200)


class Score(StrictModel):
    schema_version: Literal[1] = 1
    title: str = Field(default="Untitled", max_length=200)
    part: str = Field(default="Solo", max_length=100)
    audit_status: Literal["synthetic", "reviewed", "unreviewed"] = "unreviewed"
    provenance: str = Field(default="user-provided", max_length=300)
    pitch_domain: Literal["written", "concert"] = "concert"
    transpose_semitones: int = Field(default=0, ge=-36, le=36)
    tempo_bpm: float = Field(default=100, ge=20, le=300)
    events: list[Note] = Field(min_length=1, max_length=4096)

    @model_validator(mode="after")
    def validate_timeline(self):
        previous_end = 0.0
        ids = set()
        pitched = 0
        for n in self.events:
            if n.event_id in ids:
                raise ValueError("event_id must be unique, including repeat occurrences")
            ids.add(n.event_id)
            if n.start < previous_end - 1e-7:
                raise ValueError("events must be ordered and monophonic; expand repeats before upload")
            previous_end = n.start + n.duration
            if n.pitch is not None:
                p = self.concert_pitch(n)
                if not 12 <= p <= 120:
                    raise ValueError("transposed pitch outside supported MIDI range 12..120")
                pitched += 1
        if not pitched:
            raise ValueError("score must contain at least one pitched event")
        if self.pitch_domain == "concert" and self.transpose_semitones:
            raise ValueError("concert-pitch scores must have transpose_semitones=0")
        return self

    def concert_pitch(self, n: Note) -> float | None:
        if n.pitch is None:
            return None
        return n.pitch + (self.transpose_semitones if self.pitch_domain == "written" else 0)

    @property
    def digest(self) -> str:
        raw = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()


class Options(StrictModel):
    a4_hz: float = Field(default=440, ge=400, le=480)
    start_event_id: str | None = Field(default=None, max_length=100)
    allow_unreviewed: bool = False
    beam_width: int = Field(default=48, ge=8, le=128)
    silence_hold_s: float = Field(default=0.6, ge=0.2, le=3)


class CreateSession(StrictModel):
    score: Score
    options: Options = Field(default_factory=Options)

    @model_validator(mode="after")
    def gate(self):
        if self.score.audit_status == "unreviewed" and not self.options.allow_unreviewed:
            raise ValueError("unreviewed score requires explicit allow_unreviewed=true; this is not an audit")
        if self.options.start_event_id and self.options.start_event_id not in {
            e.event_id for e in self.score.events if e.pitch is not None
        }:
            raise ValueError("start_event_id must name a pitched event")
        return self


class Feature(StrictModel):
    type: Literal["feature"] = "feature"
    epoch: int = Field(ge=1, le=2**32 - 1)
    seq: int = Field(ge=0, le=2**32 - 1)
    sample_index: int = Field(ge=0, le=2**48)
    pitch_midi: float | None = Field(default=None, ge=12, le=120)
    clarity: float = Field(default=1, ge=0, le=1)
    rms: float = Field(default=0.1, ge=0, le=1)
    onset: bool = False
