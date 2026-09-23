"""Standalone CLI boundary for the fuyomi score-reading workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile


def add_fuyomi_parser(subparsers) -> None:
    parser = subparsers.add_parser("fuyomi", help="Read, review and audition a monophonic instrumental score")
    commands = parser.add_subparsers(dest="fuyomi_command", required=True)
    init = commands.add_parser("init", help="Register immutable source PDF and selected pages")
    init.add_argument("--source", type=Path, required=True)
    init.add_argument("--out", type=Path, required=True)
    init.add_argument("--pages", required=True, help="One-based pages, e.g. 2-5,8")
    init.add_argument("--title", required=True)
    init.add_argument("--part", required=True)
    init.add_argument("--clef", choices=("ALTO", "TENOR", "TREBLE", "BASS"), required=True)
    init.add_argument("--fifths", type=int, default=0, help="Initial key: sharps positive, flats negative")
    init.add_argument("--meter", default="4/4")
    init.add_argument("--image-mode", choices=("render", "embedded"), default="render")
    init.add_argument("--dpi", type=int, default=300)
    for name, help_text in (
        ("recognize", "Run Audiveris with restartable per-page caches, then import candidates"),
        ("import-omr", "Import saved one-page Audiveris .omr files and create review drafts"),
        ("review", "Render raw candidate IDs outside the original staff"),
        ("build", "Validate reviewed inputs and generate PDF, player, CSV, JSON and report"),
        ("validate", "Check source bindings, rhythm, ties, repeats and output checksums"),
        ("bundle", "Package source images, OMR, reviews and the current build for reproduction"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("workspace", type=Path)
        if name in ("recognize", "import-omr"):
            command.add_argument("--engine-version", required=True, help="Declared Audiveris version for the receipt")
        if name == "recognize":
            command.add_argument("--audiveris", type=Path, required=True)
            command.add_argument("--timeout", type=int, default=600, help="Seconds per page")
        elif name == "import-omr":
            command.add_argument("--omr", action="append", required=True, help="PAGE=/path/to/page.omr (repeat per page)")
        elif name == "build":
            command.add_argument("--font", type=Path, help="TrueType font supporting the title/part characters")
        elif name == "validate":
            command.add_argument("--source", type=Path, help="Also verify the original PDF checksum")
            command.add_argument("--strict", action="store_true", help="Exit 2 if any review issue remains")
        elif name == "bundle":
            command.add_argument("--out", type=Path, required=True)


def run(args: argparse.Namespace) -> int:
    from . import workflow
    from .render import render_candidate_review

    try:
        if args.fuyomi_command == "init":
            report = workflow.init_workspace(args.source, args.out, workflow.parse_pages(args.pages),
                                            title=args.title, part=args.part, clef=args.clef, fifths=args.fifths,
                                            meter=list(map(int, args.meter.split("/"))), image_mode=args.image_mode, dpi=args.dpi)
        elif args.fuyomi_command == "recognize":
            report = workflow.recognize(args.workspace, args.audiveris, args.engine_version, args.timeout)
            report["review_page"] = str(render_candidate_review(args.workspace))
        elif args.fuyomi_command == "import-omr":
            sources = {}
            for value in args.omr:
                page, path = value.split("=", 1)
                if int(page) in sources:
                    raise ValueError("Duplicate OMR page")
                sources[int(page)] = Path(path)
            report = workflow.import_omr(args.workspace, sources, args.engine_version)
            report["review_page"] = str(render_candidate_review(args.workspace))
        elif args.fuyomi_command == "review":
            workflow.load_inputs(args.workspace)
            report = {"review_page": str(render_candidate_review(args.workspace))}
        elif args.fuyomi_command == "build":
            report = workflow.build(args.workspace, font=args.font)
        elif args.fuyomi_command == "validate":
            report = workflow.validate(args.workspace, source=args.source)
        else:
            report = workflow.bundle(args.workspace, args.out)
    except ImportError as exc:
        raise RuntimeError("Install optional dependencies: pip install Pillow pypdf reportlab") from exc
    except (KeyError, TypeError, ZeroDivisionError, ET.ParseError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        raise ValueError(f"Invalid fuyomi input or external-tool failure: {exc}") from exc
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if args.fuyomi_command == "validate" and args.strict and report["issues"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuyomi")
    commands = parser.add_subparsers(dest="command", required=True)
    add_fuyomi_parser(commands)
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
        return 2
