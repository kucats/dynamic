#!/usr/bin/env python3
"""Build and validate the composer catalog using its shared offline tools."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from collections.abc import Sequence


ROOT = Path(__file__).resolve().parents[2]
COMMANDS = {
    "build": ("tools/build_catalog.py", "tools/validate_catalog.py"),
    "validate": ("tools/validate_catalog.py",),
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args(argv)
    for relative in COMMANDS[args.command]:
        result = subprocess.run([sys.executable, str(ROOT / relative)], cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
