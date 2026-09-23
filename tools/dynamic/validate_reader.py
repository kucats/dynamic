#!/usr/bin/env python3
"""Validate DYNAMIC reader data (public/reader/parts.json + public/reader/data/*.json).

Checks: schema fields, note/system references, bar labels vs. note bars, playback timeline coverage,
rhythm sanity (onset + duration inside the bar), embedded-image type, and machine-local path leaks.
Exit code 0 when valid.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RANGE = re.compile(r"^(\d+)(?:–(\d+))?$")


def check_part(entry: dict) -> list[str]:
    errs: list[str] = []
    path = ROOT / "public" / entry["data"]
    if not path.is_file():
        return [f"missing data file {entry['data']}"]
    text = path.read_text(encoding="utf-8")
    for marker in ("/" + "Users/", "/" + "home/", "file" + "://", "/" + "private/tmp/"):
        if marker in text:
            errs.append(f"{entry['id']}: machine-local path marker {marker!r}")
    d = json.loads(text)
    for key in ("id", "title", "movements", "systems", "notes", "status", "limitations", "source"):
        if key not in d:
            errs.append(f"{entry['id']}: missing {key}")
    if errs:
        return errs
    if d["id"] != entry["id"]:
        errs.append(f"{entry['id']}: id mismatch")
    if entry.get("pdf") and not (ROOT / "public" / entry["pdf"]).is_file():
        errs.append(f"{entry['id']}: missing PDF {entry['pdf']}")
    mv_keys = [m["key"] for m in d["movements"]]
    for s in d["systems"]:
        if s["mvt"] not in mv_keys:
            errs.append(f"{d['id']}: system {s['i']} has unknown movement")
        if not s["img"].startswith("data:image/png;base64,"):
            errs.append(f"{d['id']}: system {s['i']} image must be an embedded derivative PNG")
        last = 0
        for xa, xb, lab in s["segs"]:
            if xb <= xa:
                errs.append(f"{d['id']}: system {s['i']} has an empty bar segment at {xa}")
            if lab:
                m = RANGE.match(lab)
                if not m:
                    errs.append(f"{d['id']}: bad bar label {lab!r}")
                    continue
                lo = int(m.group(1))
                if lo < last:
                    errs.append(f"{d['id']}: bar labels not increasing in system {s['i']} ({lab})")
                last = int(m.group(2) or lo)
    ids = set()
    for n in d["notes"]:
        if n["id"] in ids:
            errs.append(f"{d['id']}: duplicate note id {n['id']}")
        ids.add(n["id"])
        sy = d["systems"][n["s"]]
        if sy["mvt"] != n["mvt"]:
            errs.append(f"{d['id']}: note {n['id']} movement differs from its system")
        if not (0 <= n["x"] <= sy["w"] and 0 <= n["y"] <= sy["h"]):
            errs.append(f"{d['id']}: note {n['id']} outside its system image")
        seg = [g for g in sy["segs"] if g[0] <= n["x"] < g[1]]
        if not seg or not seg[0][2]:
            errs.append(f"{d['id']}: note {n['id']} (bar {n['bar']}) is not inside a numbered bar")
        else:
            m = RANGE.match(seg[0][2])
            lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
            if not lo <= n["bar"] <= hi:
                errs.append(f"{d['id']}: note {n['id']} bar {n['bar']} but printed segment {seg[0][2]}")
        for k in ("w", "f", "snd"):
            if not (isinstance(n[k], list) and len(n[k]) == 3 and 20 <= n[k][2] <= 100):
                errs.append(f"{d['id']}: note {n['id']} bad {k} label")
    for m in d["movements"]:
        lens = {b: ln for b, ln, _spw, _ds in m["timeline"]}
        for n in (x for x in d["notes"] if x["mvt"] == m["key"]):
            if n["bar"] not in lens:
                errs.append(f"{d['id']}: note {n['id']} bar {n['bar']} missing from timeline")
            elif n["off"] + n["dur"] > lens[n["bar"]] + 1e-6:
                errs.append(f"{d['id']}: note {n['id']} overruns bar {n['bar']}")
    return errs


def main() -> int:
    idx = json.loads((ROOT / "public/reader/parts.json").read_text(encoding="utf-8"))
    errs = []
    seen = set()
    for entry in idx["parts"]:
        if entry["id"] in seen:
            errs.append(f"duplicate part {entry['id']}")
        seen.add(entry["id"])
        errs += check_part(entry)
    for e in errs:
        print("ERROR:", e)
    if not errs:
        print(f"PASS: {len(idx['parts'])} reader parts valid")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
