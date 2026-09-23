#!/usr/bin/env python3
"""Forward Fuyomi score-reading commands to the vEdit CLI without a shell."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence


USAGE = "Usage: score_reading.py <vEdit fuyomi command and arguments>"


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments in (["-h"], ["--help"]):
        print(USAGE)
        print("Example: score_reading.py init --help")
        return 0 if arguments else 2
    result = subprocess.run(["vedit", "specialized", "fuyomi", *arguments], check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
