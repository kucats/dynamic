#!/usr/bin/env python3
"""Validate the full-score viewer data (public/score/index.json + public/score/<id>/index.json).

Checks: catalog entries, page images exist and are WebP derivatives (no PDFs), bar numbers run 1..last in
every movement without gaps or repeats, bar boxes lie inside the page image, the movement totals match
the reviewed score.json, and no machine-local paths leak. Exit code 0 when valid.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def check(entry: dict) -> list[str]:
    errs: list[str] = []
    path = ROOT / "public" / entry["index"]
    if not path.is_file():
        return [f"missing {entry['index']}"]
    text = path.read_text(encoding="utf-8")
    for marker in ("/" + "Users/", "/" + "home/", "file" + "://", "/" + "private/tmp/"):
        if marker in text:
            errs.append(f"{entry['id']}: machine-local path marker {marker!r}")
    d = json.loads(text)
    for key in ("id", "title", "work", "source", "status", "limitations", "movements", "pages"):
        if key not in d:
            errs.append(f"{entry['id']}: missing {key}")
    if errs:
        return errs
    if d["id"] != entry["id"] or d["work"] != entry["work"]:
        errs.append(f"{entry['id']}: catalog entry does not match index")
    cfgs = [p for p in ROOT.glob("project/**/full-score/score.json")
            if json.loads(p.read_text(encoding="utf-8"))["id"] == d["id"]]
    expected = {}
    if cfgs:
        expected = {m["key"]: m.get("last_bar") for m in json.loads(cfgs[0].read_text(encoding="utf-8"))["movements"]}
    seen: dict[str, list[int]] = {}
    for p in d["pages"]:
        img = p["img"].split("?")[0]
        f = path.parent / img
        if not img.endswith(".webp") or not f.is_file():
            errs.append(f"{d['id']}: page {p['pdf']} image missing or not WebP ({p['img']})")
        elif f.read_bytes()[8:12] != b"WEBP":
            errs.append(f"{d['id']}: page {p['pdf']} image is not a WebP file")
        for s in p["systems"]:
            if not 0 <= s["y0"] < s["y1"] <= p["h"]:
                errs.append(f"{d['id']}: page {p['pdf']} system outside the image")
            for x0, x1, bar in s["bars"]:
                if not 0 <= x0 < x1 <= p["w"]:
                    errs.append(f"{d['id']}: page {p['pdf']} bar {bar} outside the image")
                seen.setdefault(p["mvt"], []).append(bar)
    for m in d["movements"]:
        bars = seen.get(m["key"], [])
        if bars != list(range(1, len(bars) + 1)):
            errs.append(f"{d['id']}: movement {m['key']} bars are not 1..n in page order")
        if bars and bars[-1] != m["last"]:
            errs.append(f"{d['id']}: movement {m['key']} last bar {bars[-1]} != {m['last']}")
        if expected.get(m["key"]) and m["last"] != expected[m["key"]]:
            errs.append(f"{d['id']}: movement {m['key']} ends at {m['last']}, reviewed total is {expected[m['key']]}")
    if list((path.parent).rglob("*.pdf")):
        errs.append(f"{d['id']}: PDF files must not be published with the score viewer")
    return errs


def main() -> int:
    path = ROOT / "public/score/index.json"
    if not path.exists():
        print("PASS: no score viewer data")
        return 0
    errs: list[str] = []
    cat = json.loads(path.read_text(encoding="utf-8"))["scores"]
    for entry in cat:
        errs += check(entry)
    for e in errs:
        print("ERROR:", e)
    if not errs:
        print(f"PASS: {len(cat)} score(s) valid")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
