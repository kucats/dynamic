"""Real localhost HTTP/WS + ICE/DTLS/Opus media. No mocked WebRTC connections."""

import asyncio
import json
import socket
import time
from fractions import Fraction

import av
import httpx
import numpy as np
import pytest
import pytest_asyncio
import uvicorn
import websockets
from aiortc import AudioStreamTrack, RTCConfiguration, RTCPeerConnection, RTCSessionDescription

from scorefollow.fixtures import demo_score, synthesize
from scorefollow.runtime import HEADER, Settings
from scorefollow.server import create_app


@pytest_asyncio.fixture
async def live_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    port = sock.getsockname()[1]
    app = create_app(Settings(dev=True))
    server = uvicorn.Server(
        uvicorn.Config(
            app, log_level="error", ws="auto", proxy_headers=False, lifespan="on", ws_max_size=65536
        )
    )
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        for _ in range(200):
            if server.started:
                break
            await asyncio.sleep(0.01)
        assert server.started
        yield f"http://127.0.0.1:{port}", app
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 5)
        sock.close()


async def session_info(base):
    async with httpx.AsyncClient(base_url=base) as http:
        r = await http.post("/v1/sessions", json={"score": demo_score().model_dump()})
        r.raise_for_status()
        return r.json()


def ws_url(base, info):
    return base.replace("http:", "ws:") + info["ws_path"]


async def auth(ws, info, mode):
    await ws.send(json.dumps(dict(type="auth", protocol="sfs.v1", mode=mode, token=info["token"])))
    ready = json.loads(await asyncio.wait_for(ws.recv(), 5))
    assert ready["type"] == "ready", ready
    return ready


async def collect(ws, rows, errors):
    async for raw in ws:
        message = json.loads(raw)
        if message["type"] == "position":
            rows.append(message)
        if message["type"] == "error":
            errors.append(message)


@pytest.mark.integration
async def test_actual_websocket_pcm_to_position(live_server):
    base, app = live_server
    info = await session_info(base)
    audio, _ = synthesize(demo_score())
    pcm = (audio * 32767).astype("<i2")
    rows, errors = [], []
    async with websockets.connect(ws_url(base, info), max_size=65536) as ws:
        ready = await auth(ws, info, "pcm")
        reader = asyncio.create_task(collect(ws, rows, errors))
        try:
            started = time.monotonic()
            for seq, start in enumerate(range(0, len(pcm), 320)):
                chunk = pcm[start : start + 320]
                if len(chunk) < 160:
                    break
                await asyncio.sleep(max(0, started + start / 16000 - time.monotonic()))
                await ws.send(HEADER.pack(b"SFS1", ready["epoch"], seq, start) + chunk.tobytes())
            await asyncio.sleep(0.15)
        finally:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
    assert not errors
    notes = {r["position"]["event_id"] for r in rows if r["position"]}
    assert "n015" in notes and len(notes) >= 15, notes
    assert any(r["position"] and r["position"]["confirmed"] for r in rows)
    assert max(r["dropped_packets"] for r in rows) == 0
    await asyncio.sleep(0.05)
    assert app.state.registry.sessions[info["session_id"]].owner is None


class FixtureTrack(AudioStreamTrack):
    """A real paced RTP source, no inference features/ground-truth sent to server."""

    def __init__(self):
        super().__init__()
        audio, _ = synthesize(demo_score())
        self.audio = (audio * 32767).astype("<i2")
        self.pos, self.start_time = 0, None

    async def recv(self):
        if self.start_time is None:
            self.start_time = time.monotonic()
        await asyncio.sleep(max(0, self.start_time + self.pos / 16000 - time.monotonic()))
        samples = np.zeros(320, dtype="<i2")
        available = self.audio[self.pos : self.pos + 320]
        samples[: len(available)] = available
        frame = av.AudioFrame.from_ndarray(samples.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate, frame.time_base, frame.pts = 16000, Fraction(1, 16000), self.pos
        self.pos += 320
        return frame


@pytest.mark.integration
async def test_actual_webrtc_opus_and_datachannel(live_server):
    base, app = live_server
    info = await session_info(base)
    pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    track = FixtureTrack()
    pc.addTrack(track)
    dc = pc.createDataChannel("positions", ordered=False, maxRetransmits=0)
    dc_rows, rows, errors = [], [], []

    @dc.on("message")
    def message(raw):
        dc_rows.append(json.loads(raw))

    try:
        async with websockets.connect(ws_url(base, info), max_size=65536) as ws:
            await auth(ws, info, "webrtc")
            await pc.setLocalDescription(await pc.createOffer())
            await ws.send(json.dumps({"type": "offer", "sdp": pc.localDescription.sdp}))
            while True:
                result = json.loads(await asyncio.wait_for(ws.recv(), 15))
                assert result["type"] != "error", result
                if result["type"] == "answer":
                    break
            await pc.setRemoteDescription(RTCSessionDescription(sdp=result["sdp"], type="answer"))
            reader = asyncio.create_task(collect(ws, rows, errors))
            try:
                async with asyncio.timeout(14):
                    while not any(r["position"] and r["position"]["event_id"] == "n015" for r in rows):
                        assert not errors, errors
                        await asyncio.sleep(0.05)
                assert pc.connectionState == "connected"
                assert dc_rows and any(r["type"] == "position" for r in dc_rows)
                seen = {r["position"]["event_id"] for r in rows if r["position"]}
                assert len(seen) >= 14, seen
                # Seek must re-anchor without resetting the ongoing RTP clock/peer.
                before = rows[-1]["generation"]
                await ws.send(json.dumps({"type": "seek", "event_id": "n000"}))
                await asyncio.sleep(0.3)
                assert pc.connectionState == "connected"
                assert any(r["generation"] > before for r in rows)
                assert not errors
            finally:
                reader.cancel()
                await asyncio.gather(reader, return_exceptions=True)
    finally:
        track.stop()
        await pc.close()
    await asyncio.sleep(0.1)
    s = app.state.registry.sessions[info["session_id"]]
    assert s.pc is None and not s.rtc_tasks


@pytest.mark.integration
async def test_rtc_rejects_invalid_sdp(live_server):
    base, _ = live_server
    info = await session_info(base)
    async with websockets.connect(ws_url(base, info)) as ws:
        await auth(ws, info, "webrtc")
        await ws.send(json.dumps({"type": "offer", "sdp": "not sdp"}))
        message = json.loads(await ws.recv())
        assert message["type"] == "error"
