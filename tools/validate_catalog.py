#!/usr/bin/env python3
"""Validate the composer catalog and Fuyomi project catalog together."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from catalog_lib import validate_catalog as validate_composer_catalog

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors = validate_composer_catalog(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Composer catalog valid: paths, metadata, HTML links, and hashes match.")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/validate_fuyomi_catalog.py")],
        cwd=ROOT,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
