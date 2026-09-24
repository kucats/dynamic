import numpy as np
import pytest
from pydantic import ValidationError

from scorefollow.audio import HOP, Observation, StreamingAudio, yin_pitch
from scorefollow.fixtures import demo_score, synthesize
from scorefollow.follower import Follower
from scorefollow.schema import CreateSession, Note, Options, Score


def run_audio(score, audio):
    dsp, follower = StreamingAudio(), Follower(score)
    trace = []
    for start in range(0, len(audio), HOP):
        for obs in dsp.push(audio[start : start + HOP], start):
            trace.append(follower.consume(obs))
    return trace


@pytest.mark.parametrize("midi", [29, 36, 43, 48, 60, 69, 81, 90])
def test_pitch(midi):
    t = np.arange(2048) / 16000
    x = 0.2 * np.sin(2 * np.pi * 440 * 2 ** ((midi - 69) / 12) * t)
    p, c = yin_pitch(x)
    assert p == pytest.approx(midi, abs=0.1)
    assert c > 0.9


def test_silence():
    dsp, f = StreamingAudio(), Follower(demo_score())
    for i in range(100):
        for o in dsp.push(np.zeros(HOP), i * HOP):
            state = f.consume(o)
    assert state["position"] is None
    assert state["confidence"] == 0


def test_synthetic_end_to_end():
    score = demo_score()
    audio, labels = synthesize(score)
    trace = run_audio(score, audio)
    good = 0
    for label in labels:
        near = min(trace, key=lambda r: abs(r["audio_time_s"] - label["onset_s"] - 0.25))
        if near["position"] and near["position"]["event_id"] == label["event_id"]:
            good += 1
    assert good >= len(labels) - 1, (
        good,
        [(r["audio_time_s"], r["pitch_midi"], r["position"]) for r in trace[::20]],
    )
    assert trace[-1]["status"] == "holding"


@pytest.mark.parametrize("scale", [0.7, 1.3])
def test_tempo(scale):
    s = demo_score()
    audio, labels = synthesize(s, tempo_scale=scale)
    trace = run_audio(s, audio)
    label = labels[-1]
    r = min(trace, key=lambda r: abs(r["audio_time_s"] - label["onset_s"] - 0.25 / scale))
    assert r["position"]["event_id"] == label["event_id"]


def test_written_horn_transposition():
    d = demo_score().model_dump()
    for n in d["events"]:
        if n["pitch"] is not None:
            n["pitch"] += 7
    d.update(pitch_domain="written", transpose_semitones=-7)
    s = Score.model_validate(d)
    audio, _ = synthesize(s)
    assert run_audio(s, audio)[-1]["position"]["event_id"] == "n015"


def test_repeat_skip_reacquisition():
    s = demo_score()
    f = Follower(s)
    order = list(range(8)) + list(range(2, 8)) + list(range(11, 16))
    for k, i in enumerate(order):
        p = s.concert_pitch([e for e in s.events if e.pitch is not None][i])
        r = f.consume(Observation((k + 1) * 0.5, p, 1, 0.1, True))
    assert r["position"]["event_id"] == "n015"
    assert r["status"] == "tracking"


def test_ambiguous_passage_not_confirmed():
    notes = [Note(event_id=f"n{i}", start=i, duration=1, pitch=60 + i % 3) for i in range(18)]
    f = Follower(Score(events=notes, audit_status="synthetic"))
    for k in range(3):
        r = f.consume(Observation((k + 1) * 0.6, 60 + k, 1, 0.1, True))
    assert not r["position"]["confirmed"]
    assert r["confidence"] < 0.55


def test_bad_extra_note_no_teleport():
    f = Follower(demo_score())
    for k, p in enumerate([48, 50, 55, 52, 89, 57, 53, 53, 60]):
        r = f.consume(Observation((k + 1) * 0.5, p, 1, 0.1, True))
        if p == 89:
            assert r["confidence"] < 0.1
    assert r["position"]["event_id"] == "n007"


def test_gap_invalidates_confidence():
    f = Follower(demo_score())
    for k, p in enumerate([48, 50, 55]):
        f.consume(Observation((k + 1) * 0.5, p, 1, 0.1, True))
    f.discontinuity()
    assert f.snapshot()["status"] == "lost"
    assert f.snapshot()["confidence"] == 0


def test_timestamp_regression_rejected():
    f = Follower(demo_score())
    f.consume(Observation(1, None, 0, 0))
    with pytest.raises(ValueError):
        f.consume(Observation(0.9, 60, 1, 0.1, True))


def test_score_guards():
    s = demo_score().model_dump()
    s["events"][1]["event_id"] = s["events"][0]["event_id"]
    with pytest.raises(ValidationError):
        Score.model_validate(s)
    s = demo_score().model_dump()
    s["events"][1]["start"] = 0
    with pytest.raises(ValidationError):
        Score.model_validate(s)
    s = demo_score().model_dump()
    s["tempo_bpm"] = float("nan")
    with pytest.raises(ValidationError):
        Score.model_validate(s)


def test_unreviewed_gate():
    d = demo_score().model_dump()
    d["audit_status"] = "unreviewed"
    with pytest.raises(ValidationError):
        CreateSession(score=Score.model_validate(d))
    assert CreateSession(score=Score.model_validate(d), options=Options(allow_unreviewed=True))


def test_chunk_boundary_invariance():
    s = demo_score()
    audio, _ = synthesize(s)
    a = StreamingAudio()
    b = StreamingAudio()
    left, right = [], []
    for i in range(0, len(audio), 320):
        left.extend(a.push(audio[i : i + 320], i))
    for i in range(0, len(audio), 177):
        right.extend(b.push(audio[i : i + 177], i))
    assert left == right


def collect_onsets(score):
    audio, _ = synthesize(score)
    dsp = StreamingAudio()
    onsets = []
    for start in range(0, len(audio), HOP):
        onsets.extend(obs for obs in dsp.push(audio[start : start + HOP], start) if obs.onset)
    return onsets


def test_articulation_detects_same_pitch_reattacks_without_silence():
    score = Score(
        audit_status="synthetic",
        tempo_bpm=120,
        events=[Note(event_id=f"n{i}", start=i, duration=1, pitch=62) for i in range(4)],
    )
    onsets = collect_onsets(score)
    assert len(onsets) == 4
    assert all(obs.pitch == pytest.approx(62, abs=0.15) for obs in onsets)


def test_articulation_detects_semitone_steps_without_chasing_pitch():
    score = Score(
        audit_status="synthetic",
        tempo_bpm=120,
        events=[
            Note(event_id="a", start=0, duration=1, pitch=59),
            Note(event_id="b", start=1, duration=1, pitch=60),
            Note(event_id="c", start=2, duration=1, pitch=61),
        ],
    )
    onsets = collect_onsets(score)
    assert len(onsets) == 3
    assert [round(obs.pitch) for obs in onsets] == [59, 60, 61]
