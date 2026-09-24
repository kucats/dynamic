"""Adversarial inputs and measured synthetic baselines, not real-world accuracy claims."""

import asyncio
import json
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from scorefollow.adapters import ImportError, from_musicxml
from scorefollow.audio import Observation
from scorefollow.evaluate import benchmark, grade, read_wav, replay_array
from scorefollow.fixtures import demo_score, write_fixture
from scorefollow.follower import Follower
from scorefollow.runtime import HEADER, Session, Settings
from scorefollow.schema import CreateSession
from scorefollow.server import BodyLimit, create_app


def test_offline_roundtrip_and_metrics(tmp_path):
    write_fixture(tmp_path)
    wav = read_wav(tmp_path / "performance.wav")
    rows, metrics = replay_array(demo_score(), wav)
    result = grade(rows, json.loads((tmp_path / "labels.json").read_text()))
    assert result["detected_notes"] == 16
    assert result["post_attack_200ms_accuracy"] >= 0.95
    assert metrics["frames"] > 400


def test_benchmark_reports_difficult_scenarios_without_hiding_abstentions(tmp_path):
    results = benchmark(tmp_path)
    assert len(results) == 8
    assert all(r["exact"] <= r["frames"] for r in results)
    assert all(r["post_attack_frames"] < r["frames"] for r in results)
    assert any(r["detected_notes"] < r["total_notes"] for r in results)


def test_invalid_labels_and_empty_audio_are_explicit():
    with pytest.raises(ValueError):
        grade([], [{"onset_s": float("nan"), "offset_s": 1, "event_id": "n000"}])
    with pytest.raises(ValueError):
        replay_array(demo_score(), np.zeros(0))


def test_nonfinite_http_inputs_do_not_crash_or_echo_score():
    with TestClient(create_app(Settings(dev=True))) as client:
        data = {"score": demo_score().model_dump()}
        data["score"]["events"][0]["pitch"] = float("nan")
        r = client.post(
            "/v1/sessions", content=json.dumps(data), headers={"Content-Type": "application/json"}
        )
        assert r.status_code == 422
        assert "NaN" not in r.text


async def test_chunked_body_limit_without_content_length():
    called = []

    async def inner(scope, receive, send):
        called.append(True)

    chunks = iter(
        [
            {"type": "http.request", "body": b"x" * (1024 * 1024), "more_body": True},
            {"type": "http.request", "body": b"x" * (1024 * 1024 + 1), "more_body": False},
        ]
    )

    async def receive():
        return next(chunks)

    sent = []

    async def send(message):
        sent.append(message)

    await BodyLimit(inner)({"type": "http", "method": "POST"}, receive, send)
    assert not called and sent[0]["status"] == 413


async def test_expiry_fences_previously_valid_token():
    s = Session(CreateSession(score=demo_score()), Settings(dev=True))
    try:
        s.authenticate(s.token)
        s.created = time.monotonic() - 7201
        with pytest.raises(ValueError, match="expired"):
            s.authenticate(s.token)
    finally:
        await s.close()


async def test_old_dequeued_generation_cannot_publish_after_seek():
    s = Session(CreateSession(score=demo_score()), Settings(dev=True, enforce_pacing=False))
    try:
        await s.claim("a", "webrtc")
        await s.lock.acquire()
        s.pcm(HEADER.pack(b"SFS1", s.epoch, 0, 0) + bytes(640))
        await asyncio.sleep(0.01)  # worker now holds a dequeued old-generation item, waiting for lock
        old = s.generation
        s.generation += 1
        s.lock.release()
        await asyncio.sleep(0.01)
        assert old < s.generation and s.processed == 0
    finally:
        if s.lock.locked():
            s.lock.release()
        await s.close()


def test_long_rest_does_not_claim_future_position():
    follower = Follower(demo_score())
    follower.consume(Observation(0.1, 48, 1, 0.1, True))
    before = follower.snapshot()["position"]["event_id"]
    for i in range(1, 301):
        follower.consume(Observation(0.1 + i * 0.02, None, 0, 0))
    result = follower.snapshot()
    assert result["status"] == "holding" and result["confidence"] == 0
    assert result["position"]["event_id"] == before and not result["position"]["confirmed"]


def test_larger_score_stays_bounded():
    base = demo_score().model_dump()
    events = []
    for i in range(4096):
        events.append(dict(event_id=f"n{i}", pitch=48 + i % 12, start=i, duration=0.8))
    base["events"] = events
    f = Follower(CreateSession.model_validate({"score": base}).score)
    for i in range(10):
        f.consume(Observation(0.1 + i * 0.5, 48 + i % 12, 1, 0.1, True))
    assert len(f.beam) <= 48


def test_xml_invalid_voice_and_navigation_fail_closed():
    for body in [
        "<note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice></note><note><rest/><duration>1</duration><voice>2</voice></note>",
        '<direction><sound dacapo="yes"/></direction>',
    ]:
        with pytest.raises(ImportError):
            from_musicxml(
                f'<score-partwise><part id="p"><measure number="1">{body}</measure></part></score-partwise>'.encode()
            )
