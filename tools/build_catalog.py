#!/usr/bin/env python3
"""Build both the composer guide pages and the Fuyomi project catalog."""

from build_composer_catalog import build as build_composer_catalog
from build_fuyomi_catalog import main as build_fuyomi_catalog


def main() -> None:
    build_composer_catalog()
    build_fuyomi_catalog()


if __name__ == "__main__":
    main()
