import asyncio
import json

import av
import numpy as np
import pytest
from scipy.io import wavfile

from scorefollow.audio import Observation
from scorefollow.fixtures import demo_score
from scorefollow.follower import Follower
from scorefollow.recording import load_recording
from scorefollow.recording_lab import diagnostic
from scorefollow.reference import ChromaFrame, ChromaStream, ReferenceTracker, features, match_window
from scorefollow.runtime import HEADER, ProtocolError, Session, Settings, Subscriber
from scorefollow.schema import CreateSession


def waveform(seconds=2, rate=16000):
    t = np.arange(round(seconds * rate)) / rate
    x = 0.2 * np.sin(2 * np.pi * 220 * t)
    return x.astype(np.float32)


def test_float_media_retains_headroom_channels_and_private_metadata(tmp_path):
    x = np.stack((waveform() * 6, -waveform() * 6), axis=1)
    path = tmp_path / "secret-venue.wav"
    wavfile.write(path, 16000, x)
    r = load_recording(path)
    assert r.samples.shape == x.shape
    assert np.max(np.abs(r.samples)) > 1.1
    assert np.allclose(r.samples, x)
    assert np.max(abs(r.channel("mix"))) == 0
    profile = r.profile()
    assert profile["channel_correlation"] == pytest.approx(-1)
    assert profile["accuracy"] is None and profile["alignment_status"] == "unlabeled"
    assert str(tmp_path) not in json.dumps(profile) and "secret-venue" not in json.dumps(profile)
    assert len(profile["source_sha256"]) == 64


def test_aac_stereo_48k_real_encode_decode(tmp_path):
    path = tmp_path / "original.m4a"
    audio = waveform(1, 48000)
    with av.open(str(path), "w", format="ipod") as out:
        stream = out.add_stream("aac", rate=48000)
        stream.layout = "stereo"
        for start in range(0, len(audio), 960):
            frame = av.AudioFrame.from_ndarray(
                np.stack((audio[start : start + 960], audio[start : start + 960] * 0.5)),
                format="fltp",
                layout="stereo",
            )
            frame.sample_rate = 48000
            frame.pts = start
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)
    r = load_recording(path)
    assert r.source_rate == 48000 and r.codec == "aac"
    assert r.samples.shape[1] == 2 and 0.98 <= len(r.samples) / 16000 <= 1.04
    ratio = np.std(r.samples[:, 1]) / np.std(r.samples[:, 0])
    assert 0.45 < ratio < 0.55


def test_media_bounds_and_unsupported_inputs(tmp_path):
    path = tmp_path / "tone.wav"
    wavfile.write(path, 16000, waveform())
    with pytest.raises(ValueError, match="duration"):
        load_recording(path, max_seconds=0.5)
    with pytest.raises(ValueError, match="byte"):
        load_recording(path, max_bytes=100)
    for name in ("remote.m3u8", "remote.sdp", "remote.xml"):
        p = tmp_path / name
        p.write_text("http://169.254.169.254/")
        with pytest.raises(ValueError):
            load_recording(p)
    linked = tmp_path / "link.wav"
    linked.symlink_to(path)
    with pytest.raises(ValueError):
        load_recording(linked)
    with pytest.raises(ValueError):
        load_recording(path, timestamp_policy="guess")
    mono = load_recording(path)
    with pytest.raises(ValueError):
        mono.channel("right")
    assert diagnostic(mono)["accuracy"] is None


def test_chroma_stereo_power_does_not_cancel_antiphase():
    x = waveform()
    c, times, rms = features(x)
    stereo, st, srms = features(np.stack((x, -x), axis=1))
    assert np.allclose(c, stereo) and np.allclose(rms, srms)
    assert np.array_equal(times, st)
    assert np.max(c) > 0.5
    assert times[0] == 0.256


def test_chroma_chunk_invariance_and_gap_fencing():
    x = waveform()
    a, b = ChromaStream(), ChromaStream()
    left = a.push(x, 0)
    right = []
    for i in range(0, len(x), 173):
        right.extend(b.push(x[i : i + 173], i))
    assert len(left) == len(right)
    for before, after in zip(left, right):
        assert before.time == after.time and np.array_equal(before.chroma, after.chroma)
    with pytest.raises(ValueError, match="gap"):
        b.push(x[:320], len(x) + 320)
    b.reset()
    assert b.push(x[:4096], 10000)[0].time == (10000 + 4096) / 16000


def reference_fixture():
    rng = np.random.default_rng(426)
    x = rng.random((800, 12)).astype(np.float32)
    x /= np.linalg.norm(x, axis=1, keepdims=True)
    return x


def test_subsequence_dtw_recovers_midreference_without_start_hint():
    r = reference_fixture()
    q = r[200:350]
    best = match_window(q, r)[0]
    assert best["cost"] < 1e-6
    assert best["reference_start_s"] == pytest.approx(20.256)
    assert best["reference_end_s"] == pytest.approx(35.156)


@pytest.mark.parametrize(
    "value", [np.full((5, 12), np.nan), np.ones((5, 11)), -np.ones((5, 12)), np.ones((5, 12))]
)
def test_invalid_chroma_rejected(value):
    with pytest.raises(ValueError):
        match_window(value, reference_fixture())


def test_tracker_causal_prefix_invariance_and_unknown_score_position():
    r = reference_fixture()
    frames = [ChromaFrame(0.256 + i * 0.1, c, 0.1) for i, c in enumerate(r[200:520])]
    a, b = ReferenceTracker(r), ReferenceTracker(r)
    left = [row for frame in frames[:250] if (row := a.consume(frame))]
    right = [row for frame in frames if (row := b.consume(frame))]
    assert left == right[: len(left)]
    assert right[-1]["status"] == "tracking_candidate"
    assert right[-1]["reference_time_s"] == pytest.approx(52.156)
    assert right[-1]["score_position"] is None and right[-1]["confirmed"] is False
    with pytest.raises(ValueError, match="continuous"):
        b.consume(ChromaFrame(100, r[0], 0.1))


def test_silence_and_constant_chord_do_not_lock():
    r = reference_fixture()
    for level, feature in ((0, np.zeros(12)), (0.1, r[5])):
        tracker = ReferenceTracker(r)
        result = None
        for i in range(240):
            result = tracker.consume(ChromaFrame(0.256 + i * 0.1, feature, level)) or result
        assert result["status"] != "tracking_candidate"
        assert not result["confirmed"]


def test_wrong_current_sound_cannot_keep_previous_onset_confirmed():
    f = Follower(demo_score())
    for i, pitch in enumerate((48, 50, 55, 52)):
        f.consume(Observation(0.5 + i * 0.5, pitch, 1, 0.1, True))
    assert f.snapshot()["position"]["confirmed"]
    result = f.consume(Observation(2.02, 77, 1, 0.1, False))
    assert result["status"] == "uncertain"
    assert not result["position"]["confirmed"]
    result = f.consume(Observation(2.04, None, 0, 0, False))
    assert not result["position"]["confirmed"]


async def test_reference_session_cannot_claim_note_or_apply_unmapped_seek():
    session = Session(
        CreateSession(score=demo_score()),
        Settings(dev=True, enforce_pacing=False),
        reference_chroma=reference_fixture(),
    )
    try:
        await session.claim("owner", "pcm")
        assert session.snapshot()["position"] is None
        with pytest.raises(ProtocolError, match="anchors"):
            await session.control({"type": "seek", "event_id": "n000"})
        # Test bounded worker output using a deterministic 4s tracker for this unit fixture.
        session.reference_tracker = ReferenceTracker(reference_fixture(), window_frames=40)
        sub = Subscriber()
        session.subscribers.add(sub)
        audio = waveform(5)
        for i in range(0, len(audio), 1600):
            session.pcm(
                HEADER.pack(b"SFS1", session.epoch, i // 1600, i)
                + (audio[i : i + 1600] * 32767).astype("<i2").tobytes()
            )
            while session.processed_end is None or session.processed_end < i + 1600:
                await asyncio.sleep(0.001)
        messages = []
        while not sub.queue.empty():
            messages.append(sub.queue.get_nowait())
        refs = [m for m in messages if m["type"] == "reference_position"]
        assert refs and refs[-1]["score_position"] is None
        assert refs[-1]["epoch"] == session.epoch
        assert not refs[-1]["confirmed"]
        await session.control({"type": "pause"})
        assert session.snapshot()["status"] == "paused"
        assert not session.reference_tracker.frames
        await session.control({"type": "resume"})
        assert not session.reference_tracker.frames
    finally:
        await session.close()


def test_identical_reference_passages_cannot_lock_from_copied_audio():
    a = reference_fixture()[:260]
    r = np.concatenate((a, a, a))
    tracker = ReferenceTracker(r)
    for i, c in enumerate(a[:250]):
        result = tracker.consume(ChromaFrame(0.256 + i * 0.1, c, 0.1))
        if result:
            assert result["status"] != "tracking_candidate"


def test_constant_dc_profile_is_finite(tmp_path):
    path = tmp_path / "dc.wav"
    wavfile.write(path, 16000, np.full((16000, 2), .1, dtype=np.float32))
    profile = load_recording(path).profile()
    assert profile["channel_correlation"] is None
    json.dumps(profile, allow_nan=False)


def test_impossible_reference_length_is_rejected_before_alignment():
    r = reference_fixture()
    with pytest.raises(ValueError, match="short"):
        match_window(r[:100], r[:10])
    with pytest.raises(ValueError, match="short"):
        ReferenceTracker(r[:30])
