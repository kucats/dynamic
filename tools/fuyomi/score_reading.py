#!/usr/bin/env python3
"""Compatibility entry point for the standalone local Fuyomi CLI."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.fuyomi import cli


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] != "fuyomi":
        arguments.insert(0, "fuyomi")
    return cli.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
