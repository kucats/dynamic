"""Bounded per-session ownership, audio timelines, backpressure and lifecycle."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from collections import deque
from dataclasses import dataclass

import numpy as np

from .audio import HOP, SAMPLE_RATE, WINDOW, Observation, StreamingAudio
from .follower import Follower
from .schema import CreateSession, Feature
from .reference import ChromaStream, ReferenceTracker

HEADER = struct.Struct("<4sIIQ")
MAX_PCM_BYTES = HEADER.size + 3200


class ProtocolError(ValueError):
    pass


@dataclass
class Settings:
    api_key: str = ""
    dev: bool = False
    origins: tuple[str, ...] = ("http://127.0.0.1:8765", "http://localhost:8765")
    max_sessions: int = 8
    ttl_s: float = 1800
    idle_s: float = 90
    queue_size: int = 8
    enforce_pacing: bool = True
    stun_urls: tuple[str, ...] = ()
    turn_urls: tuple[str, ...] = ()
    turn_secret: str = ""

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.getenv("SF_API_KEY", ""),
            dev=os.getenv("SF_DEV") == "1",
            origins=tuple(
                x
                for x in os.getenv("SF_ORIGINS", "http://127.0.0.1:8765,http://localhost:8765").split(",")
                if x
            ),
            max_sessions=int(os.getenv("SF_MAX_SESSIONS", "8")),
            ttl_s=float(os.getenv("SF_SESSION_TTL", "1800")),
            idle_s=float(os.getenv("SF_IDLE_TIMEOUT", "90")),
            stun_urls=tuple(x for x in os.getenv("SF_STUN_URLS", "").split(",") if x),
            turn_urls=tuple(x for x in os.getenv("SF_TURN_URLS", "").split(",") if x),
            turn_secret=os.getenv("SF_TURN_SECRET", ""),
        )

    def validate(self):
        if not self.dev and len(self.api_key) < 32:
            raise ValueError("SF_API_KEY must contain at least 32 characters outside loopback dev mode")
        if "*" in self.origins or not 1 <= self.max_sessions <= 128:
            raise ValueError("explicit origins and max_sessions=1..128 required")
        if not 1 <= self.queue_size <= 32 or not 1 <= self.idle_s <= self.ttl_s <= 7200:
            raise ValueError("invalid queue or session timeout limits")
        if self.turn_urls and len(self.turn_secret) < 32:
            raise ValueError("TURN URLs require SF_TURN_SECRET with at least 32 characters")
        if any(not u.startswith(("stun:", "stuns:")) for u in self.stun_urls):
            raise ValueError("invalid STUN URL scheme")
        if any(not u.startswith(("turn:", "turns:")) for u in self.turn_urls):
            raise ValueError("invalid TURN URL scheme")

    def ice_servers(self, session_id: str) -> list[dict]:
        ice = [{"urls": list(self.stun_urls)}] if self.stun_urls else []
        if self.turn_urls:
            expiry = int(time.time() + self.ttl_s + 30)
            username = f"{expiry}:{session_id}"
            credential = base64.b64encode(
                hmac.new(self.turn_secret.encode(), username.encode(), hashlib.sha1).digest()
            ).decode()
            ice.append({"urls": list(self.turn_urls), "username": username, "credential": credential})
        return ice


class Subscriber:
    def __init__(self):
        self.queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=16)
        self.closed = False

    def offer(self, event: dict):
        # Coalesce position updates; never let a slow UI queue minutes of old positions.
        saved = []
        while not self.queue.empty():
            item = self.queue.get_nowait()
            if event["type"] not in ("position", "reference_position") or item["type"] != event["type"]:
                saved.append(item)
        for item in saved:
            self.queue.put_nowait(item)
        if self.queue.full():
            self.closed = True
            return
        self.queue.put_nowait(event)


class Session:
    def __init__(self, request: CreateSession, settings: Settings, acoustic_factory=StreamingAudio, reference_chroma=None):
        self.id = secrets.token_hex(16)
        self.token = secrets.token_urlsafe(32)
        self.request, self.settings = request, settings
        self.created = self.touched = time.monotonic()
        self.epoch = 0
        self.generation = 0
        self.revision = 0
        self.owner: str | None = None
        self.mode: str | None = None
        self.closed = False
        self.lock = asyncio.Lock()
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=settings.queue_size)
        self.subscribers: set[Subscriber] = set()
        self.dsp = acoustic_factory(request.options.a4_hz)
        self.follower = Follower(request.score, request.options)
        self.reference_dsp = ChromaStream() if reference_chroma is not None else None
        self.reference_tracker = ReferenceTracker(reference_chroma) if reference_chroma is not None else None
        self.reference_digest = hashlib.sha256(reference_chroma.astype("<f4").tobytes()).hexdigest() if reference_chroma is not None else None
        self.pending_reference = None
        self.last_seq = -1
        self.received_end = 0
        self.processed_end: int | None = None
        self.credit = 0.3
        self.credit_time = time.monotonic()
        self.dropped = 0
        self.processed = 0
        self.compute_ms: deque[float] = deque(maxlen=256)
        self.last_emit = -1.0
        self.pc = None
        self.rtc_tasks: set[asyncio.Task] = set()
        self.data_channel = None
        self.task = asyncio.create_task(self._worker())

    def _reset_reference(self):
        self.pending_reference = None
        if self.reference_tracker:
            self.reference_tracker.reset()
            self.reference_dsp.reset()

    def snapshot(self):
        result = self.follower.snapshot()
        if self.reference_tracker:
            # No reviewed reference->score anchors exist in this version.
            result.update(position=None, alternatives=[], confidence=0.0,
                          status="paused" if self.follower.paused else "reference_only")
        return result

    def authenticate(self, token: str):
        if self.closed or time.monotonic() - self.created >= self.settings.ttl_s:
            raise ProtocolError("session_expired")
        if not secrets.compare_digest(token, self.token):
            raise ProtocolError("unauthorized")
        self.touched = time.monotonic()

    async def claim(self, owner: str, mode: str) -> int:
        async with self.lock:
            if self.closed or self.owner is not None:
                raise ProtocolError("input_already_owned")
            self.owner, self.mode = owner, mode
            self._new_epoch()
            return self.epoch

    def _new_epoch(self, event_id: str | None = None):
        self.epoch += 1
        self.generation += 1
        self.credit, self.credit_time = 0.3, time.monotonic()
        self.last_seq, self.received_end, self.processed_end = -1, 0, None
        self.dsp.reset()
        self._reset_reference()
        self.follower.reset(event_id or self.request.options.start_event_id)
        self.last_emit = -1
        while not self.queue.empty():
            self.queue.get_nowait()

    async def release(self, owner: str):
        async with self.lock:
            if self.owner != owner:
                return
            self.owner = self.mode = None
            self.generation += 1
            self.epoch += 1  # Fence already-decoded media from the old peer immediately.
            self.follower.discontinuity()
            self._reset_reference()
            while not self.queue.empty():
                self.queue.get_nowait()
            pc, self.pc = self.pc, None
            tasks = list(self.rtc_tasks)
            self.rtc_tasks.clear()
            self.data_channel = None
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if pc:
            await pc.close()

    def publish(self, event: dict):
        self.revision += 1
        event = {**event, "epoch": self.epoch, "generation": self.generation, "revision": self.revision}
        for subscriber in tuple(self.subscribers):
            subscriber.offer(event)
        if event["type"] in ("position", "reference_position") and self.data_channel:
            if self.data_channel.readyState == "open" and self.data_channel.bufferedAmount < 16384:
                import json

                self.data_channel.send(json.dumps(event, separators=(",", ":"), allow_nan=False))

    def _check_packet(self, epoch: int, seq: int, start: int, count: int):
        if self.closed or self.owner is None:
            raise ProtocolError("no_input_owner")
        if epoch != self.epoch:
            raise ProtocolError("stale_epoch")
        if start > 2**48 or seq <= self.last_seq or start < self.received_end:
            raise ProtocolError("replayed_or_out_of_order_packet")
        if start - self.received_end > 30 * SAMPLE_RATE:
            raise ProtocolError("audio_gap_too_large_reconnect_required")
        now = time.monotonic()
        self.credit = min(0.3, self.credit + (now - self.credit_time) * 1.25)
        self.credit_time = now
        if self.settings.enforce_pacing and count / SAMPLE_RATE > self.credit + 1e-6:
            raise ProtocolError("audio_rate_exceeded_use_offline_evaluator")
        self.credit = max(0, self.credit - count / SAMPLE_RATE)
        self.last_seq, self.received_end = seq, start + count
        self.touched = now

    def _enqueue(self, kind: str, payload, start: int):
        if self.queue.full():
            self.queue.get_nowait()
            self.dropped += 1
        self.queue.put_nowait((self.epoch, self.generation, kind, payload, start, time.monotonic()))

    def pcm(self, raw: bytes):
        if self.mode not in ("pcm", "webrtc") or not HEADER.size + 320 <= len(raw) <= MAX_PCM_BYTES:
            raise ProtocolError("invalid_pcm_size_or_mode")
        if (len(raw) - HEADER.size) % 2:
            raise ProtocolError("unaligned_pcm")
        magic, epoch, seq, start = HEADER.unpack_from(raw)
        if magic != b"SFS1":
            raise ProtocolError("invalid_pcm_magic")
        count = (len(raw) - HEADER.size) // 2
        self._check_packet(epoch, seq, start, count)
        samples = np.frombuffer(raw, dtype="<i2", offset=HEADER.size).astype(np.float32) / 32768
        self._enqueue("pcm", samples, start)

    def feature(self, feature: Feature):
        if self.mode != "features":
            raise ProtocolError("invalid_feature_mode")
        self._check_packet(feature.epoch, feature.seq, feature.sample_index, HOP)
        self._enqueue("feature", feature, feature.sample_index)

    def _compute(self, kind, payload, start):
        if (self.processed_end is not None and start != self.processed_end) or (
            self.processed_end is None and self.last_emit < 0 and start > 0
        ):
            self.dsp.reset()
            self.follower.discontinuity()
            self._reset_reference()
        self.pending_reference = None
        if kind == "pcm":
            if self.reference_tracker and not self.follower.paused:
                for frame in self.reference_dsp.push(payload, start):
                    candidate = self.reference_tracker.consume(frame)
                    if candidate:
                        self.pending_reference = {**candidate, "reference_sha256": self.reference_digest}
            observations = self.dsp.push(payload, start)
            self.processed_end = start + len(payload)
        else:
            observations = [
                Observation(
                    (start + HOP) / SAMPLE_RATE,
                    payload.pitch_midi,
                    payload.clarity,
                    payload.rms,
                    payload.onset,
                )
            ]
            self.processed_end = start + HOP
        results = [self.follower.consume(o) for o in observations]
        return self.snapshot() if results else None

    async def _worker(self):
        try:
            while not self.closed:
                epoch, generation, kind, payload, start, enqueued = await self.queue.get()
                async with self.lock:
                    if (
                        epoch != self.epoch
                        or generation != self.generation
                        or self.owner is None
                        or self.closed
                    ):
                        continue
                    begin = time.monotonic()
                    previous_onsets = self.follower.observations
                    result = await asyncio.to_thread(self._compute, kind, payload, start)
                    elapsed = (time.monotonic() - begin) * 1000
                    self.compute_ms.append(elapsed)
                    self.processed += 1
                    if self.pending_reference:
                        self.publish(self.pending_reference)
                        self.pending_reference = None
                    if result and (
                        result["audio_time_s"] - self.last_emit >= 0.10 - 1e-6
                        or self.follower.observations != previous_onsets
                    ):
                        self.last_emit = result["audio_time_s"]
                        self.publish(
                            {
                                **result,
                                "processing_ms": round(elapsed, 3),
                                "queue_ms": round((begin - enqueued) * 1000, 3),
                                "window_ms": WINDOW / SAMPLE_RATE * 1000,
                                "dropped_packets": self.dropped,
                            }
                        )
        except asyncio.CancelledError:
            raise
        except Exception:
            # No raw frame, token, SDP or user text in error reports.
            self.publish({"type": "error", "code": "processing_failed"})
            await self.close("processing_failed")

    async def control(self, message: dict):
        op = message.get("type")
        async with self.lock:
            if op == "seek":
                if self.reference_tracker:
                    raise ProtocolError("reference_mode_requires_reviewed_score_anchors")
                event_id = message.get("event_id")
                if event_id not in {n.event_id for n in self.follower.notes}:
                    raise ProtocolError("unknown_event_id")
                if self.mode == "webrtc":
                    # RTP timestamps continue. Re-anchor inference, not the RTP packet clock.
                    self.generation += 1
                    self.follower.reset(event_id)
                    self.last_emit = self.received_end / SAMPLE_RATE
                    self.dsp.reset()
                    self.processed_end = None
                    while not self.queue.empty():
                        self.queue.get_nowait()
                else:
                    self._new_epoch(event_id)
            elif op == "pause":
                self._reset_reference()
                self.follower.paused = True
            elif op == "resume":
                self.generation += 1
                while not self.queue.empty():
                    self.queue.get_nowait()
                self.follower.paused = False
                self.follower.discontinuity()
                self.dsp.reset()
                self._reset_reference()
            else:
                raise ProtocolError("unknown_control")
            self.publish({"type": "ack", "command": op})

    async def close(self, reason: str = "closed"):
        if self.closed:
            return
        self.closed = True
        self.publish({"type": "closed", "reason": reason})
        if self.owner:
            await self.release(self.owner)
        if self.task is not asyncio.current_task():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)


class Registry:
    def __init__(self, settings: Settings, acoustic_factory=StreamingAudio, reference_chroma=None):
        self.settings = settings
        self.acoustic_factory = acoustic_factory
        self.reference_chroma = ReferenceTracker(reference_chroma).reference.copy() if reference_chroma is not None else None
        if self.reference_chroma is not None:
            self.reference_chroma.setflags(write=False)
        self.sessions: dict[str, Session] = {}
        self.created_count = 0

    def create(self, request: CreateSession) -> Session:
        if len(self.sessions) >= self.settings.max_sessions:
            raise ProtocolError("session_capacity_exceeded")
        session = Session(request, self.settings, self.acoustic_factory, self.reference_chroma)
        self.sessions[session.id] = session
        self.created_count += 1
        return session

    async def reap(self):
        now = time.monotonic()
        for sid, session in list(self.sessions.items()):
            if (
                session.closed
                or now - session.created >= self.settings.ttl_s
                or now - session.touched >= self.settings.idle_s
            ):
                await session.close("expired")
                self.sessions.pop(sid, None)

    async def close(self):
        await asyncio.gather(*(s.close("server_shutdown") for s in self.sessions.values()))
        self.sessions.clear()
