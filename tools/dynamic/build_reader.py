#!/usr/bin/env python3
"""Build DYNAMIC reader data (public/reader/data/<id>.json) from a part's reviewed page data.

Inputs (committed):
  project/<composer>/<work>/<part>/dynamic/part.json          movement / tempo / page configuration
  project/<composer>/<work>/<part>/dynamic/pages/notes_pNN.json  per-page notes (pitch, rhythm, bar, position)
  project/<composer>/<work>/<part>/dynamic/pages/bars_pNN.json   per-page barline segments with bar numbers
Input (NOT committed): the user-supplied source PDF. Pages are rendered at 300 dpi into --work.

Usage:
  python3 tools/dynamic/build_reader.py --pdf /path/to/source.pdf [--work work] [part_dir ...]
Without part_dir arguments every project/**/dynamic/part.json is built.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HORN_KEYS, label, parse_pitch, staves, transpose  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "public/reader/data"
CROP_X = (170, 2790)          # horizontal crop of the 300-dpi page (keeps clef and final barline)


def render_page(pdf: Path, page: int, work: Path) -> Path:
    png = work / f"p{page}.png"
    if not png.exists():
        work.mkdir(parents=True, exist_ok=True)
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", "300", "-png", "-singlefile", "-gray",
                        str(pdf), str(work / f"p{page}")], check=True)
    return png


def crop_system(im: np.ndarray, s: list[float], first: bool) -> tuple[np.ndarray, int]:
    top = max(0, int(s[0]) - (200 if first else 150))
    bot = min(im.shape[0], int(s[4]) + 100)
    c = im[top:bot, CROP_X[0]:CROP_X[1]].copy()
    bb = (c < 215).astype(np.uint8)
    nl, lab, stt, _ = cv2.connectedComponentsWithStats(bb, connectivity=8)
    st_top = s[0] - top
    for li in range(1, nl):
        x_, y_, w_, h_, _a = stt[li]
        touches = y_ == 0 or y_ + h_ >= c.shape[0]
        foreign = (not first) and y_ + h_ < st_top - 88     # markings of the previous system
        if (touches or foreign) and w_ < 1500:
            c[lab == li] = 255
    c[c > 200] = 255
    ink = np.where((c < 128).sum(1) > 2)[0]          # trim empty margins above / below the system
    if len(ink):
        t0 = max(0, int(ink[0]) - 10)
        t1 = min(c.shape[0], int(ink[-1]) + 12)
        t0 = min(t0, int(s[0]) - top - 30)
        t1 = max(t1, int(s[4]) - top + 40)
        c = c[t0:t1]
        top += t0
    return c, top


def png_b64(arr: np.ndarray) -> str:
    img = Image.fromarray(arr).convert("L").quantize(colors=16, dither=Image.Dither.NONE)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def meter_len(m: str) -> float:
    return float(Fraction(m))


def at(pairs, bar):
    v = pairs[0][1]
    for b, x in pairs:
        if b <= bar:
            v = x
    return v


def build(part_dir: Path, pdf: Path, work: Path) -> dict:
    cfg = json.loads((part_dir / "part.json").read_text(encoding="utf-8"))
    pages = sorted({p for m in cfg["movements"] for p in m["pages"]})
    splits = {s["page"]: s for s in cfg.get("splits", [])}
    systems, notes = [], []
    for page in pages:
        im = cv2.imread(str(render_page(pdf, page, work)), cv2.IMREAD_GRAYSCALE)
        ST = staves(im < 140)
        data = json.loads((part_dir / f"pages/notes_p{page:02d}.json").read_text(encoding="utf-8"))
        bars = json.loads((part_dir / f"pages/bars_p{page:02d}.json").read_text(encoding="utf-8"))
        mv_here = [m["key"] for m in cfg["movements"] if page in m["pages"]]
        sys_index = {}
        for si, s in enumerate(ST, 1):
            mv = mv_here[0]
            if page in splits and si >= splits[page]["first_system"]:
                mv = splits[page]["movement"]
            crop, top = crop_system(im, s, si == 1)
            segs = [[round(g["xa"] - CROP_X[0]), round(g["xb"] - CROP_X[0]), g.get("label", "")]
                    for g in bars.get(str(si), [])]
            sys_index[si] = len(systems)
            systems.append(dict(i=len(systems), mvt=mv, page=page, sys=si, w=crop.shape[1], h=crop.shape[0],
                                top=top, staff=[round(v - top, 1) for v in s], segs=segs, img=png_b64(crop)))
        for n in data["notes"]:
            si = min(range(len(ST)), key=lambda k: abs(n["y"] - (ST[k][0] + ST[k][4]) / 2)) + 1
            sy = systems[sys_index[si]]
            L, a, o = parse_pitch(n["pitch"])
            old = n.get("notation") == "old-bass-clef"
            wo = o + 1 if old else o          # old notation bass clef is written an octave low
            key = n.get("horn_key") or cfg.get("default_horn_key", "F")
            dl, ds = HORN_KEYS[key]
            s_ = transpose(L, a, wo, dl, ds)
            f_ = transpose(*s_, 4, 7)
            notes.append(dict(
                s=sy["i"], mvt=sy["mvt"], x=round(n["x"] - CROP_X[0], 1), y=round(n["y"] - sy["top"], 1),
                bar=n["bar"], off=float(Fraction(n["off"])), dur=float(Fraction(n["dur"])),
                tie=bool(n.get("tie_from_prev")), unc=n.get("uncertain") or "", key=key,
                w=label(L, a, wo), f=label(*f_), snd=label(*s_), old=old, p=n["pitch"]))
    for i, n in enumerate(notes):
        n["id"] = i + 1
    movements = []
    for m in cfg["movements"]:
        seq = []
        for a, b in m.get("sequence", [[1, m["last"]]]):
            seq.append(list(range(a, b + 1)))
        timeline, ds = [], False
        for k, part in enumerate(seq):
            for b in part:
                timeline.append([b, meter_len(at(m["meters"], b)), round(240.0 / at(m["tempos"], b), 5),
                                 1 if (k == 1 and len(seq) == 3) else 0])
        movements.append(dict(key=m["key"], title=m["title"], last=m["last"], timeline=timeline,
                              notes=sum(1 for n in notes if n["mvt"] == m["key"])))
    for s in systems:
        del s["top"]
    out = dict(schema=1, id=cfg["id"], title=cfg["title"], subtitle=cfg["subtitle"], composer=cfg["composer"],
               work=cfg["work"], part=cfg["part"], source=cfg["source"], status=cfg["status"],
               limitations=cfg["limitations"], pdf=cfg.get("pdf"), movements=movements,
               systems=systems, notes=notes)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--work", default=Path("work"), type=Path)
    ap.add_argument("parts", nargs="*", type=Path)
    args = ap.parse_args()
    digest = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    part_dirs = args.parts or sorted(p.parent for p in ROOT.glob("project/**/dynamic/part.json"))
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for pd in part_dirs:
        cfg = json.loads((pd / "part.json").read_text(encoding="utf-8"))
        if cfg["source"]["sha256"] != digest:
            raise SystemExit(f"{pd}: source PDF hash mismatch ({digest})")
        data = build(pd, args.pdf, args.work)
        (OUT / f"{data['id']}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                                                 encoding="utf-8")
        index.append(dict(id=data["id"], title=data["title"], subtitle=data["subtitle"], part=data["part"],
                          work=data["work"], composer=data["composer"], status=data["status"], pdf=data["pdf"],
                          movements=[dict(key=m["key"], title=m["title"], notes=m["notes"]) for m in data["movements"]],
                          notes=len(data["notes"]), data=f"reader/data/{data['id']}.json"))
        print(f"built {data['id']}: {len(data['notes'])} notes, {len(data['systems'])} systems")
    existing = []
    idx_path = ROOT / "public/reader/parts.json"
    if args.parts and idx_path.exists():
        existing = [p for p in json.loads(idx_path.read_text(encoding="utf-8"))["parts"]
                    if p["id"] not in {i["id"] for i in index}]
    idx_path.write_text(json.dumps(dict(schema=1, parts=existing + index), ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")


if __name__ == "__main__":
    main()
