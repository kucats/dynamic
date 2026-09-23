#!/usr/bin/env python3
"""Validate catalog metadata, repository paths, hashes, and generated links."""

from pathlib import Path

from catalog_lib import validate_catalog


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors = validate_catalog(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Catalog valid: paths, metadata, HTML links, and SHA-256 hashes match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
