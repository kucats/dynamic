"""Authenticated REST lifecycle + WebSocket PCM/features/signaling/events."""

from __future__ import annotations

import asyncio
import contextlib
import json
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import __version__
from .audio import StreamingAudio
from .fixtures import demo_score
from .rtc import answer_offer
from .runtime import ProtocolError, Registry, Settings, Subscriber
from .schema import CreateSession, Feature

MAX_BODY = 2 * 1024 * 1024


class BodyLimit:
    """Bound actual ASGI bytes, including chunked HTTP and dishonest Content-Length."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope.get("method") in ("POST", "PUT", "PATCH"):
            parts, size = [], 0
            while True:
                event = await receive()
                if event["type"] == "http.disconnect":
                    return
                size += len(event.get("body", b""))
                if size > MAX_BODY:
                    return await PlainTextResponse("request_too_large", status_code=413)(scope, receive, send)
                parts.append(event.get("body", b""))
                if not event.get("more_body"):
                    break
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": b"".join(parts), "more_body": False}
                return await receive()

            await self.app(scope, replay, send)
        else:
            await self.app(scope, receive, send)


def create_app(settings: Settings | None = None, *, acoustic_factory=StreamingAudio) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.validate()
    registry = Registry(settings, acoustic_factory)

    @asynccontextmanager
    async def lifespan(_app):
        async def janitor():
            while True:
                await asyncio.sleep(1)
                await registry.reap()

        task = asyncio.create_task(janitor())
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await registry.close()

    app = FastAPI(
        title="DYNAMIC Score Following Server",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.add_middleware(BodyLimit)
    app.state.registry = registry

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, exc):
        # Never echo uploaded scores/tokens, or serialize NaN / arbitrary exception contexts.
        errors = [{"loc": list(e["loc"]), "type": e["type"], "msg": e["msg"]} for e in exc.errors()[:16]]
        return JSONResponse({"detail": errors}, status_code=422)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in settings.origins:
            return PlainTextResponse("origin_not_allowed", status_code=403)
        if (
            settings.dev
            and request.client
            and request.client.host not in ("127.0.0.1", "::1", "localhost", "testclient")
        ):
            return PlainTextResponse("development_mode_is_loopback_only", status_code=403)
        if request.method != "OPTIONS" and (
            (request.url.path == "/v1/sessions" and request.method == "POST")
            or request.url.path == "/metrics"
        ):
            if not settings.dev and not secrets.compare_digest(bearer(request.headers), settings.api_key):
                return PlainTextResponse("unauthorized", status_code=401)
        if request.method == "OPTIONS":
            response = PlainTextResponse("", status_code=204)
        else:
            response = await call_next(request)
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Authorization,Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "microphone=(self)"
        return response

    def bearer(headers) -> str:
        value = headers.get("authorization", "")
        return value[7:] if value.startswith("Bearer ") else ""

    def service_auth(request: Request):
        if not settings.dev and not secrets.compare_digest(bearer(request.headers), settings.api_key):
            raise HTTPException(401, "unauthorized")

    def session_auth(sid: str, token: str):
        s = registry.sessions.get(sid)
        try:
            if s is None:
                raise ProtocolError("unauthorized")
            s.authenticate(token)
        except ProtocolError:
            raise HTTPException(401, "unauthorized_or_expired") from None
        return s

    @app.get("/healthz")
    async def health():
        return {"status": "ok", "version": __version__, "experimental": True}

    @app.get("/v1/demo-score")
    async def demo():
        return demo_score()

    @app.post("/v1/sessions", status_code=201)
    async def create(request: Request, body: CreateSession):
        service_auth(request)
        await registry.reap()
        try:
            s = registry.create(body)
        except ProtocolError as exc:
            raise HTTPException(429, str(exc)) from None
        return {
            "session_id": s.id,
            "token": s.token,
            "protocol": "sfs.v1",
            "ws_path": f"/v1/sessions/{s.id}/ws",
            "ttl_s": settings.ttl_s,
            "ice_servers": settings.ice_servers(s.id),
            "score_sha256": body.score.digest,
        }

    @app.get("/v1/sessions/{sid}")
    async def state(sid: str, request: Request):
        s = session_auth(sid, bearer(request.headers))
        async with s.lock:
            return {
                **s.follower.snapshot(),
                "epoch": s.epoch,
                "generation": s.generation,
                "revision": s.revision,
                "processed_packets": s.processed,
                "dropped_packets": s.dropped,
            }

    @app.delete("/v1/sessions/{sid}")
    async def delete(sid: str, request: Request):
        s = session_auth(sid, bearer(request.headers))
        await s.close("deleted")
        registry.sessions.pop(sid, None)
        return {"deleted": True}

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics(request: Request):
        service_auth(request)
        return (
            f"scorefollow_sessions {len(registry.sessions)}\n"
            f"scorefollow_sessions_created_total {registry.created_count}\n"
            f"scorefollow_audio_packets_processed {sum(s.processed for s in registry.sessions.values())}\n"
            f"scorefollow_audio_packets_dropped {sum(s.dropped for s in registry.sessions.values())}\n"
        )

    @app.websocket("/v1/sessions/{sid}/ws")
    async def websocket(sid: str, ws: WebSocket):
        origin = ws.headers.get("origin")
        if origin and origin not in settings.origins:
            await ws.close(code=1008)
            return
        if (
            settings.dev
            and ws.client
            and ws.client.host not in ("127.0.0.1", "::1", "localhost", "testclient")
        ):
            await ws.close(code=1008)
            return
        await ws.accept()
        s, subscriber, sender, receive_task = None, None, None, None
        owner = secrets.token_hex(8)
        try:
            raw = await asyncio.wait_for(ws.receive_text(), 5)
            if len(raw) > 2048:
                raise ProtocolError("auth_message_too_large")
            auth = json.loads(raw)
            if not isinstance(auth, dict) or auth.get("type") != "auth" or auth.get("protocol") != "sfs.v1":
                raise ProtocolError("invalid_auth")
            if set(auth) - {"type", "protocol", "token", "mode"} or not isinstance(auth.get("token"), str):
                raise ProtocolError("invalid_auth")
            try:
                s = session_auth(sid, auth["token"])
            except HTTPException:
                raise ProtocolError("unauthorized_or_expired") from None
            mode = auth.get("mode")
            if mode not in ("pcm", "features", "webrtc", "observe"):
                raise ProtocolError("invalid_mode")
            if len(s.subscribers) >= 3:
                raise ProtocolError("subscriber_capacity_exceeded")
            if mode != "observe":
                await s.claim(owner, mode)
            subscriber = Subscriber()
            s.subscribers.add(subscriber)
            await ws.send_json(
                {
                    "type": "ready",
                    "epoch": s.epoch,
                    "generation": s.generation,
                    "mode": mode,
                    "sample_rate": 16000,
                    "channels": 1,
                    "format": "s16le",
                    "hop_samples": 320,
                    "max_packet_samples": 1600,
                    "score_sha256": s.request.score.digest,
                }
            )

            async def send_loop():
                while not subscriber.closed:
                    message = await subscriber.queue.get()
                    await asyncio.wait_for(ws.send_json(message), 2)
                    if message["type"] == "closed":
                        await ws.close(code=1000)
                        return
                await ws.close(code=1008)

            sender = asyncio.create_task(send_loop())
            credit, last = 200.0, time.monotonic()
            while not s.closed:
                receive_task = asyncio.create_task(ws.receive())
                done, _ = await asyncio.wait({receive_task, sender}, return_when=asyncio.FIRST_COMPLETED)
                if sender in done:
                    receive_task.cancel()
                    await asyncio.gather(receive_task, return_exceptions=True)
                    sender.result()
                    break
                message = receive_task.result()
                if message["type"] == "websocket.disconnect":
                    break
                now = time.monotonic()
                credit = min(200, credit + (now - last) * 150)
                last = now
                if credit < 1:
                    raise ProtocolError("message_rate_exceeded")
                credit -= 1
                s.authenticate(auth["token"])
                if message.get("bytes") is not None:
                    if mode != "pcm":
                        raise ProtocolError("binary_only_allowed_for_pcm_owner")
                    s.pcm(message["bytes"])
                    continue
                text = message.get("text", "")
                if len(text.encode()) > 50_000:
                    raise ProtocolError("message_too_large")
                data = json.loads(text)
                if not isinstance(data, dict):
                    raise ProtocolError("object_required")
                op = data.get("type")
                if op == "ping" and set(data) <= {"type", "client_time"}:
                    subscriber.offer({"type": "pong", "server_monotonic_s": now})
                elif mode == "observe":
                    raise ProtocolError("observer_is_read_only")
                elif op == "offer" and mode == "webrtc" and set(data) == {"type", "sdp"}:
                    subscriber.offer(await answer_offer(s, data["sdp"]))
                elif op == "feature" and mode == "features":
                    s.feature(Feature.model_validate(data))
                elif op in ("pause", "resume", "seek") and set(data) <= {"type", "event_id"}:
                    await s.control(data)
                else:
                    raise ProtocolError("unknown_message")
        except (ProtocolError, ValidationError, ValueError, TypeError, asyncio.TimeoutError) as exc:
            code = str(exc) if isinstance(exc, ProtocolError) else "invalid_message"
            if sender:
                sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)
            with contextlib.suppress(Exception):
                await asyncio.wait_for(ws.send_json({"type": "error", "code": code}), 2)
                await ws.close(code=1008)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            if receive_task and not receive_task.done():
                receive_task.cancel()
                await asyncio.gather(receive_task, return_exceptions=True)
            if sender:
                sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)
            if s:
                if subscriber:
                    s.subscribers.discard(subscriber)
                await s.release(owner)

    # Static lab is deliberately separate from the existing DYNAMIC reader.
    web = Path(__file__).resolve().parent / "web"
    if web.exists():
        app.mount("/", StaticFiles(directory=web, html=True), name="lab")
    return app
