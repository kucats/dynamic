from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapters import from_dynamic, from_musicxml
from .evaluate import benchmark, grade, read_wav, replay_array
from .fixtures import write_fixture
from .schema import Options, Score


def load_json(path: Path, limit: int = 2 * 1024 * 1024):
    if path.stat().st_size > limit:
        raise ValueError(f"input exceeds {limit} bytes")
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description="DYNAMIC experimental Score Following Server")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="start one stateful ASGI worker")
    serve.add_argument("--dev", action="store_true", help="loopback-only, no service API key")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    fixture = sub.add_parser("fixtures", help="write original synthetic score/WAV/labels")
    fixture.add_argument("output", type=Path)
    bench = sub.add_parser("benchmark", help="eight synthetic regression scenarios")
    bench.add_argument("output", type=Path)
    ev = sub.add_parser("evaluate", help="offline WAV -> trace and optional ground-truth metrics")
    ev.add_argument("score", type=Path)
    ev.add_argument("wav", type=Path)
    ev.add_argument("--labels", type=Path)
    ev.add_argument("--output", type=Path, required=True)
    ev.add_argument("--allow-unreviewed", action="store_true")
    ev.add_argument("--start-event-id")
    for name in ("import-dynamic", "import-musicxml"):
        imp = sub.add_parser(name)
        imp.add_argument("input", type=Path)
        imp.add_argument("output", type=Path)
        if name == "import-dynamic":
            imp.add_argument("--movement", required=True)
        else:
            imp.add_argument("--part-id")
    sub.add_parser("schema", help="emit CreateSession JSON schema")
    args = parser.parse_args()
    try:
        if args.command == "serve":
            import uvicorn
            from .runtime import Settings
            from .server import create_app

            settings = Settings.from_env()
            settings.dev = args.dev or settings.dev
            if settings.dev and args.host not in ("127.0.0.1", "::1", "localhost"):
                raise ValueError("--dev cannot bind a non-loopback address")
            uvicorn.run(
                create_app(settings),
                host=args.host,
                port=args.port,
                workers=1,
                ws_max_size=65536,
                ws_max_queue=8,
                limit_concurrency=64,
                timeout_keep_alive=5,
                proxy_headers=False,
                access_log=False,
            )
        elif args.command == "fixtures":
            write_fixture(args.output)
        elif args.command == "benchmark":
            print(json.dumps(benchmark(args.output), indent=2))
        elif args.command == "evaluate":
            score = Score.model_validate(load_json(args.score))
            rows, metrics = replay_array(
                score,
                read_wav(args.wav),
                Options(allow_unreviewed=args.allow_unreviewed, start_event_id=args.start_event_id),
            )
            if args.labels:
                metrics.update(grade(rows, load_json(args.labels)))
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "trace.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            (args.output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
            print(json.dumps(metrics, indent=2))
        elif args.command == "import-dynamic":
            score = from_dynamic(load_json(args.input, 32 * 1024 * 1024), args.movement)
            args.output.write_text(score.model_dump_json(indent=2) + "\n")
        elif args.command == "import-musicxml":
            if args.input.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("MusicXML exceeds 2 MiB")
            score = from_musicxml(args.input.read_bytes(), args.part_id)
            args.output.write_text(score.model_dump_json(indent=2) + "\n")
        elif args.command == "schema":
            from .schema import CreateSession

            print(json.dumps(CreateSession.model_json_schema(), indent=2))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
