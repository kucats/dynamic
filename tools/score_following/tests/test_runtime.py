import asyncio
import json
import struct
import time

import pytest
from fastapi.testclient import TestClient

from scorefollow.fixtures import demo_score
from scorefollow.runtime import HEADER, ProtocolError, Registry, Session, Settings, Subscriber
from scorefollow.schema import CreateSession, Feature
from scorefollow.server import create_app


def request():
    return CreateSession(score=demo_score())


def packet(epoch=1, seq=0, start=0, count=320):
    return HEADER.pack(b"SFS1", epoch, seq, start) + bytes(count * 2)


async def test_single_input_and_fencing():
    s = Session(request(), Settings(dev=True, enforce_pacing=False))
    try:
        assert await s.claim("a", "pcm") == 1
        with pytest.raises(ProtocolError, match="owned"):
            await s.claim("b", "features")
        s.pcm(packet())
        with pytest.raises(ProtocolError, match="replayed"):
            s.pcm(packet())
        await s.release("a")
        await s.claim("b", "pcm")
        with pytest.raises(ProtocolError, match="stale_epoch"):
            s.pcm(packet())
        s.pcm(packet(epoch=s.epoch))
    finally:
        await s.close()
    assert s.task.done()


async def test_overflow_is_bounded_and_gap_is_not_silence():
    s = Session(request(), Settings(dev=True, queue_size=2, enforce_pacing=False))
    try:
        await s.claim("a", "pcm")
        for i in range(10):
            s.pcm(packet(seq=i, start=i * 320))
        assert s.queue.qsize() == 2 and s.dropped == 8
        await asyncio.sleep(0.04)
        assert s.follower.gaps == 1
        assert s.follower.confidence == 0
    finally:
        await s.close()


async def test_seek_generations_and_pause():
    s = Session(request(), Settings(dev=True, enforce_pacing=False))
    try:
        await s.claim("a", "pcm")
        old = s.epoch
        await s.control({"type": "seek", "event_id": "n005"})
        assert s.epoch > old
        with pytest.raises(ProtocolError):
            s.pcm(packet(epoch=old))
        await s.control({"type": "pause"})
        assert s.follower.snapshot()["status"] == "paused"
        await s.control({"type": "resume"})
        assert s.follower.snapshot()["confidence"] == 0
        await s.release("a")
        await s.claim("b", "webrtc")
        generation, epoch = s.generation, s.epoch
        s.pcm(packet(epoch=epoch))
        await s.control({"type": "seek", "event_id": "n003"})
        assert s.generation == generation + 1 and s.epoch == epoch
        assert s.queue.empty()
    finally:
        await s.close()


async def test_pcm_validation_and_rate():
    s = Session(request(), Settings(dev=True))
    try:
        await s.claim("a", "pcm")
        for bad in [b"bad", packet(count=1), packet(count=1601), b"XXXX" + packet()[4:], packet() + b"\x00"]:
            with pytest.raises(ProtocolError):
                s.pcm(bad)
        with pytest.raises(ProtocolError):
            s.pcm(packet(start=2**50))
        with pytest.raises(ProtocolError):
            s.pcm(packet(start=31 * 16000))
        s.pcm(packet(count=1600))
        s.pcm(packet(seq=1, start=1600, count=1600))
        s.pcm(packet(seq=2, start=3200, count=1600))
        with pytest.raises(ProtocolError, match="rate"):
            s.pcm(packet(seq=3, start=4800, count=1600))
    finally:
        await s.close()


async def test_registry_limits_expiry_and_cleanup():
    registry = Registry(Settings(dev=True, max_sessions=1, idle_s=1))
    s = registry.create(request())
    with pytest.raises(ProtocolError):
        registry.create(request())
    s.touched = time.monotonic() - 2
    await registry.reap()
    assert not registry.sessions and s.closed and s.task.done()


def test_subscriber_coalescing_and_control_order():
    sub = Subscriber()
    sub.offer({"type": "ack", "command": "pause"})
    for i in range(100):
        sub.offer({"type": "position", "revision": i})
    assert sub.queue.qsize() == 2
    assert sub.queue.get_nowait()["command"] == "pause"
    assert sub.queue.get_nowait()["revision"] == 99
    for _ in range(17):
        sub.offer({"type": "ack"})
    assert sub.closed


def test_turn_credentials_are_ephemeral():
    cfg = Settings(api_key="a" * 32, turn_urls=("turn:turn.example.test:3478",), turn_secret="x" * 32)
    cfg.validate()
    ice = cfg.ice_servers("test-session")[0]
    assert int(ice["username"].split(":")[0]) > time.time()
    assert ice["credential"] != cfg.turn_secret
    assert "x" * 32 not in json.dumps(ice)


@pytest.mark.parametrize(
    "settings",
    [
        Settings(),
        Settings(dev=True, origins=("*",)),
        Settings(dev=True, max_sessions=129),
        Settings(dev=True, turn_urls=("turn:bad",)),
    ],
)
def test_unsafe_settings_fail_closed(settings):
    with pytest.raises(ValueError):
        settings.validate()


def make_client(**kw):
    return TestClient(create_app(Settings(dev=True, enforce_pacing=False, **kw)))


def new_session(client):
    response = client.post("/v1/sessions", json=request().model_dump())
    assert response.status_code == 201, response.text
    return response.json()


def authenticate(ws, info, mode="pcm", token=None):
    ws.send_json(dict(type="auth", protocol="sfs.v1", token=token or info["token"], mode=mode))
    return ws.receive_json()


def test_http_auth_origin_limits_and_openapi():
    with TestClient(create_app(Settings(api_key="a" * 32))) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/metrics").status_code == 401
        assert client.post("/v1/sessions", json=request().model_dump()).status_code == 401
        assert (
            client.post(
                "/v1/sessions", content="bad", headers={"Authorization": "Bearer " + "a" * 32}
            ).status_code
            == 422
        )
        assert client.get("/healthz", headers={"Origin": "https://evil.test"}).status_code == 403
        assert (
            client.options("/v1/sessions", headers={"Origin": "http://localhost:8765"}).headers[
                "access-control-allow-origin"
            ]
            == "http://localhost:8765"
        )
    with make_client(max_sessions=1) as client:
        info = new_session(client)
        assert client.post("/v1/sessions", json=request().model_dump()).status_code == 429
        assert client.get("/v1/sessions/" + info["session_id"]).status_code == 401
        assert client.post("/v1/sessions", content=b" " * (2 * 1024 * 1024 + 1)).status_code == 413
        assert client.delete(
            "/v1/sessions/" + info["session_id"], headers={"Authorization": "Bearer " + info["token"]}
        ).json()["deleted"]
        new_session(client)


@pytest.mark.parametrize(
    "message",
    [None, [], {}, {"type": "auth"}, {"type": "auth", "protocol": "sfs.v1", "token": "bad", "mode": "pcm"}],
)
def test_bad_ws_auth_does_not_claim_session(message):
    with make_client() as client:
        info = new_session(client)
        with client.websocket_connect(info["ws_path"]) as ws:
            ws.send_json(message)
            assert ws.receive_json()["type"] == "error"
        with client.websocket_connect(info["ws_path"]) as ws:
            assert authenticate(ws, info)["type"] == "ready"


def test_ws_audio_ready_position_and_controls():
    with make_client() as client:
        info = new_session(client)
        with client.websocket_connect(info["ws_path"]) as ws:
            ready = authenticate(ws, info)
            assert ready["format"] == "s16le"
            for i in range(8):
                ws.send_bytes(packet(ready["epoch"], i, i * 320))
            position = ws.receive_json()
            assert position["type"] == "position" and position["position"] is None
            ws.send_json({"type": "seek", "event_id": "n002"})
            while True:
                ack = ws.receive_json()
                if ack["type"] == "ack":
                    break
            assert ack["epoch"] > ready["epoch"]
            ws.send_bytes(packet(epoch=ready["epoch"], seq=9, start=9 * 320))
            assert ws.receive_json()["code"] == "stale_epoch"


def test_observer_and_second_publisher_are_rejected():
    with make_client() as client:
        info = new_session(client)
        with client.websocket_connect(info["ws_path"]) as owner:
            authenticate(owner, info)
            with client.websocket_connect(info["ws_path"]) as second:
                assert authenticate(second, info)["code"] == "input_already_owned"
            with client.websocket_connect(info["ws_path"]) as observer:
                assert authenticate(observer, info, "observe")["type"] == "ready"
                observer.send_json({"type": "pause"})
                assert observer.receive_json()["code"] == "observer_is_read_only"
            owner.send_json({"type": "ping"})
            assert owner.receive_json()["type"] == "pong"


def test_nan_feature_rejected_and_unknown_control():
    with make_client() as client:
        info = new_session(client)
        with client.websocket_connect(info["ws_path"]) as ws:
            ready = authenticate(ws, info, "features")
            ws.send_text(
                json.dumps(
                    dict(type="feature", epoch=ready["epoch"], seq=0, sample_index=0, pitch_midi=float("nan"))
                )
            )
            assert ws.receive_json()["type"] == "error"
        with client.websocket_connect(info["ws_path"]) as ws:
            authenticate(ws, info)
            ws.send_json({"type": "offer", "sdp": "invalid"})
            assert ws.receive_json()["type"] == "error"


def test_header_contract():
    assert HEADER.size == 20
    raw = HEADER.pack(b"SFS1", 7, 42, 640)
    assert raw == b"SFS1" + struct.pack("<IIQ", 7, 42, 640)


async def test_features_use_same_follower():
    s = Session(request(), Settings(dev=True, enforce_pacing=False))
    try:
        await s.claim("a", "features")
        for i, note in enumerate([n for n in demo_score().events if n.pitch is not None][:4]):
            for frame in range(25):
                seq = i * 25 + frame
                s.feature(
                    Feature(
                        epoch=s.epoch,
                        seq=seq,
                        sample_index=seq * 320,
                        pitch_midi=note.pitch,
                        onset=frame == 0,
                    )
                )
                await asyncio.sleep(0.001)
        assert s.follower.snapshot()["position"]["event_id"] == "n003"
    finally:
        await s.close()
