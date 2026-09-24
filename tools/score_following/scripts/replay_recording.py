"""Paced private-media trial against an explicitly selected server; loopback-only by default."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlparse

import av
import httpx
import numpy as np
import websockets
from aiortc import AudioStreamTrack, RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription

from scorefollow.recording import load_recording
from scorefollow.runtime import HEADER


class ReplayTrack(AudioStreamTrack):
    def __init__(self, pcm):
        super().__init__()
        self.pcm, self.cursor, self.clock = pcm, 0, None

    async def recv(self):
        if self.clock is None:
            self.clock = time.monotonic()
        await asyncio.sleep(max(0, self.clock + self.cursor / 16000 - time.monotonic()))
        x = np.zeros(320, dtype="<i2")
        chunk = self.pcm[self.cursor : self.cursor + 320]
        x[: len(chunk)] = chunk
        frame = av.AudioFrame.from_ndarray(x[None, :], format="s16", layout="mono")
        frame.sample_rate, frame.time_base, frame.pts = 16000, Fraction(1, 16000), self.cursor
        self.cursor += 320
        return frame


async def trial(args):
    parsed = urlparse(args.base)
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        raise ValueError("explicit HTTP(S) server URL required")
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1") and not args.allow_remote_audio:
        raise ValueError("remote audio transmission requires --allow-remote-audio consent")
    if not 0 < args.seconds <= 60 or args.start < 0 or not 0 < args.gain <= 1:
        raise ValueError("trial duration must be 0..60s, start>=0, gain=0..1")
    recording = load_recording(args.recording)
    start, end = round(args.start * 16000), round((args.start + args.seconds) * 16000)
    if end > len(recording.samples):
        raise ValueError("excerpt exceeds decoded duration")
    x = recording.channel(args.channel)[start:end] * args.gain
    clipped = float(np.mean(np.abs(x) > 1))
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    headers = {"Authorization": "Bearer " + args.api_key} if args.api_key else {}
    rows, errors, pc, track = [], [], None, None
    async with httpx.AsyncClient(base_url=args.base, headers=headers, timeout=10) as http:
        score = (
            json.loads(args.score.read_text()) if args.score else (await http.get("/v1/demo-score")).json()
        )
        response = await http.post(
            "/v1/sessions", json={"score": score, "options": {"allow_unreviewed": args.allow_unreviewed}}
        )
        response.raise_for_status()
        info = response.json()
        try:
            if args.score is None and not info.get("reference_mode"):
                raise ValueError(
                    "note-following trials require --score; demo score is only a reference-mode context"
                )
            url = args.base.replace("https:", "wss:").replace("http:", "ws:").rstrip("/") + info["ws_path"]
            async with websockets.connect(url, max_size=65536) as ws:
                await ws.send(
                    json.dumps(
                        {"type": "auth", "protocol": "sfs.v1", "token": info["token"], "mode": args.transport}
                    )
                )
                ready = json.loads(await asyncio.wait_for(ws.recv(), 5))
                if ready["type"] != "ready":
                    raise ValueError("audio connection rejected")
                if args.transport == "webrtc":
                    pc = RTCPeerConnection(
                        RTCConfiguration(iceServers=[RTCIceServer(**x) for x in info["ice_servers"]])
                    )
                    track = ReplayTrack(pcm)
                    pc.addTrack(track)
                    await pc.setLocalDescription(await pc.createOffer())
                    await ws.send(json.dumps({"type": "offer", "sdp": pc.localDescription.sdp}))
                    while True:
                        message = json.loads(await asyncio.wait_for(ws.recv(), 15))
                        if message["type"] == "error":
                            raise ValueError("media negotiation failed")
                        if message["type"] == "answer":
                            break
                    await pc.setRemoteDescription(RTCSessionDescription(type="answer", sdp=message["sdp"]))

                async def collect():
                    async for raw in ws:
                        row = json.loads(raw)
                        if row["type"] in ("position", "reference_position"):
                            rows.append(row)
                        elif row["type"] == "error":
                            errors.append(row.get("code", "unknown"))

                reader = asyncio.create_task(collect())
                try:
                    if args.transport == "pcm":
                        clock = time.monotonic()
                        for seq, offset in enumerate(range(0, len(pcm) - 319, 320)):
                            await asyncio.sleep(max(0, clock + offset / 16000 - time.monotonic()))
                            await ws.send(
                                HEADER.pack(b"SFS1", ready["epoch"], seq, offset)
                                + pcm[offset : offset + 320].tobytes()
                            )
                        await asyncio.sleep(0.25)
                    else:
                        async with asyncio.timeout(args.seconds + 15):
                            while track.cursor < len(pcm) + 1600:
                                if errors:
                                    raise ValueError("server rejected media")
                                await asyncio.sleep(0.05)
                    if errors:
                        raise ValueError("server media errors: " + ",".join(errors))
                finally:
                    reader.cancel()
                    await asyncio.gather(reader, return_exceptions=True)
            if not rows:
                raise ValueError("no inference messages received")
        finally:
            if track:
                track.stop()
            if pc:
                await pc.close()
            deletion = await http.delete(
                "/v1/sessions/" + info["session_id"], headers={"Authorization": "Bearer " + info["token"]}
            )
            deletion.raise_for_status()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "trace.jsonl").open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, allow_nan=False) + "\n")
    refs = [r for r in rows if r["type"] == "reference_position"]
    summary = {
        "transport": args.transport,
        "source_sha256": recording.source_sha256,
        "excerpt_decoded_start_s": args.start,
        "seconds": args.seconds,
        "channel": args.channel,
        "gain": args.gain,
        "pcm_clip_fraction_after_gain": clipped,
        "messages": len(rows),
        "reference_messages": len(refs),
        "last_reference": refs[-1] if refs else None,
        "errors": errors,
        "deleted_session": True,
        "score_alignment_accuracy": None,
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "last_reference"}, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("recording", type=Path)
    p.add_argument("--base", default="http://127.0.0.1:8765")
    p.add_argument("--transport", choices=("pcm", "webrtc"), default="pcm")
    p.add_argument("--score", type=Path)
    p.add_argument("--allow-unreviewed", action="store_true")
    p.add_argument("--allow-remote-audio", action="store_true")
    p.add_argument("--api-key", default="")
    p.add_argument("--channel", choices=("mix", "left", "right"), default="left")
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--gain", type=float, default=0.5)
    p.add_argument("--output", type=Path, required=True)
    asyncio.run(trial(p.parse_args()))


if __name__ == "__main__":
    main()
