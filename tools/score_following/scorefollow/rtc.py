"""An actual receiving WebRTC peer, not a signaling-only placeholder."""

from __future__ import annotations

import asyncio

import av
from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError
from aiortc.sdp import SessionDescription

from .runtime import HEADER, ProtocolError, Session


async def answer_offer(session: Session, sdp: str) -> dict:
    if not isinstance(sdp, str) or len(sdp.encode()) > 48_000:
        raise ProtocolError("sdp_too_large")
    if session.pc is not None or session.mode != "webrtc":
        raise ProtocolError("peer_already_exists_or_wrong_mode")
    if len(sdp.splitlines()) > 512 or sdp.count("a=candidate:") > 64:
        raise ProtocolError("too_many_sdp_lines_or_candidates")
    try:
        parsed = SessionDescription.parse(sdp)
    except (ValueError, AssertionError, IndexError) as exc:
        raise ProtocolError("invalid_sdp") from exc
    media = [m.kind for m in parsed.media]
    if (
        media.count("audio") != 1
        or media.count("application") > 1
        or any(m not in ("audio", "application") for m in media)
    ):
        raise ProtocolError("exactly_one_audio_track_required")
    ice = [RTCIceServer(**item) for item in session.settings.ice_servers(session.id)]
    pc = RTCPeerConnection(RTCConfiguration(iceServers=ice))
    session.pc = pc
    epoch = session.epoch
    track_seen = False

    async def consume(track):
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        origin = None
        fallback = 0
        seq = 0
        try:
            while not session.closed and session.epoch == epoch:
                frame = await track.recv()
                for out in resampler.resample(frame):
                    if out.pts is not None and out.time_base is not None:
                        stamp = float(out.pts * out.time_base)
                        if origin is None:
                            origin = stamp
                        start = round((stamp - origin) * 16000)
                    else:
                        start = fallback
                    samples = out.to_ndarray().reshape(-1).astype("<i2")
                    # aiortc Opus usually yields 20ms; bound and preserve media timestamps.
                    for offset in range(0, len(samples), 1600):
                        chunk = samples[offset : offset + 1600]
                        if len(chunk) < 160:
                            # Unexpected tiny decoder fragments must not invent continuity.
                            continue
                        session.pcm(HEADER.pack(b"SFS1", epoch, seq, start + offset) + chunk.tobytes())
                        seq += 1
                    fallback = start + len(samples)
        except MediaStreamError:
            session.publish({"type": "media_ended"})
        except asyncio.CancelledError:
            raise
        except (ProtocolError, ValueError):
            session.publish({"type": "error", "code": "rtc_audio_discontinuity_reconnect"})
            await pc.close()

    @pc.on("track")
    def on_track(track):
        nonlocal track_seen
        if track_seen or track.kind != "audio":
            track.stop()
            return
        track_seen = True
        task = asyncio.create_task(consume(track))
        session.rtc_tasks.add(task)
        task.add_done_callback(session.rtc_tasks.discard)

    @pc.on("datachannel")
    def on_datachannel(channel):
        if channel.label != "positions" or session.data_channel is not None:
            channel.close()
            return
        session.data_channel = channel

        @channel.on("message")
        def on_message(_message):
            # Deliberately output-only: controls go through authenticated, ordered WS.
            channel.close()

    @pc.on("connectionstatechange")
    async def state_change():
        session.publish({"type": "rtc_state", "state": pc.connectionState})
        if pc.connectionState == "failed":
            await pc.close()

    try:
        await asyncio.wait_for(pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer")), 8)
        answer = await pc.createAnswer()
        await asyncio.wait_for(pc.setLocalDescription(answer), 10)
        return {"type": "answer", "sdp": pc.localDescription.sdp, "epoch": epoch}
    except BaseException as exc:
        await pc.close()
        session.pc = None
        for task in list(session.rtc_tasks):
            task.cancel()
        await asyncio.gather(*session.rtc_tasks, return_exceptions=True)
        session.rtc_tasks.clear()
        if isinstance(exc, asyncio.CancelledError):
            raise
        raise ProtocolError("webrtc_negotiation_failed") from exc
