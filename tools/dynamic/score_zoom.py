#!/usr/bin/env python3
"""Zoom crop of ONE staff on a full-score page, with pitch guides and bar
boundaries — the score counterpart of zoom.py (which keys off detected part
staves and candidate noteheads).

Usage:
  python3 tools/dynamic/score_zoom.py PAGE --staff N [--dpi 300] \
      [--work work/db8] [--index public/score/dvorak8/index.json] [X0 X1] [OUT]

Reads work/p<PAGE>.png (or p<PAGE>_d<DPI>.png) and work/score_staves_p<PAGE>.json
(from score_staves.py).  Draws the same left-margin pitch guides as zoom.py
(treble red/green, bass grey parens, alto purple brackets) plus vertical bar
boundaries with bar numbers (from the reviewed index when given, else the
left/right staff extent).  Writes OUT or work/score_z_p<PAGE>_s<ROW>.png.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_staves import crop_frame  # noqa: E402

LET = "CDEFGAB"


def bar_ranges(index_path: Path, page: int, im, dpi: float) -> list[tuple[float, float, int]]:
    """index.json bar x-intervals mapped into this render's pixel space."""
    idx = json.loads(index_path.read_text(encoding="utf-8"))
    pg = next(p for p in idx["pages"] if p["pdf"] == page)
    _, _, x0, x1 = crop_frame(im, dpi)
    k = (x1 - x0) / pg["w"]
    return [(x0 + a * k, x0 + b * k, lab)
            for s in pg["systems"] for a, b, lab in s["bars"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("page", type=int)
    ap.add_argument("--staff", type=int, required=True, help="staff number i from score_staves JSON")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--work", type=Path, default=Path("work"))
    ap.add_argument("--index", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("xr", nargs="*", type=int, help="optional X0 X1 render-px range")
    args = ap.parse_args()

    import cv2

    png = args.work / (f"p{args.page}_d{args.dpi}.png" if args.dpi != 300 else f"p{args.page}.png")
    staves = json.loads((args.work / f"score_staves_p{args.page}.json").read_text(encoding="utf-8"))
    rec = next(s for s in staves["staves"] if s["i"] == args.staff)
    im = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    if im is None:
        raise SystemExit(f"{png} not found")
    H, W = im.shape
    k = args.dpi / 300.0
    y5 = rec["y"]
    top = max(0, int(y5[0] - 210 * k))
    bot = min(H, int(y5[4] + 190 * k))
    x0 = int(args.xr[0]) if args.xr else 0
    x1 = int(args.xr[1]) if len(args.xr) > 1 else W

    c = cv2.cvtColor(im[top:bot, x0:x1], cv2.COLOR_GRAY2BGR)
    pad = int(230 * k)
    c = cv2.copyMakeBorder(c, int(46 * k), 0, pad, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    sp = (y5[4] - y5[0]) / 4                     # staff-line spacing px
    bl = y5[4]                                  # bottom line y (page coords)
    for j in range(-9, 18):
        y = int(bl - j * sp / 2 - top + 46 * k)
        d = 2 + j
        tn = LET[d % 7] + str(4 + d // 7)       # treble
        db = 4 + j
        bn = LET[db % 7] + str(2 + db // 7)     # bass
        da = 3 + j
        an = LET[da % 7] + str(3 + da // 7)     # alto
        colr = (0, 0, 230) if j % 2 == 0 else (0, 150, 0)
        cv2.putText(c, tn, (2, y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5 * k, colr, 1)
        cv2.putText(c, "(" + bn + ")", (int(58 * k), y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45 * k,
                    (120, 120, 120), 1)
        cv2.putText(c, "[" + an + "]", (int(124 * k), y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45 * k,
                    (170, 0, 170), 1)
        cv2.line(c, (int(185 * k), y), (pad - 2, y), colr, 1)

    bars = bar_ranges(args.index, args.page, im, args.dpi) if args.index else []
    for a, b, lab in bars:
        for x in (a, b):
            X = int(x - x0 + pad)
            if pad <= X < c.shape[1]:
                cv2.line(c, (X, 0), (X, c.shape[0]), (255, 160, 0), 1)
        xm = int((a + b) / 2 - x0 + pad)
        if pad <= xm < c.shape[1]:
            cv2.putText(c, str(lab), (xm - 10, int(20 * k)), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55 * k, (255, 0, 0), 1)
    out = args.out or args.work / f"score_z_p{args.page}_s{args.staff}.png"
    cv2.imwrite(str(out), c)
    print("wrote", out, f"sys {rec['sys']} row {rec['row']}", f"y {top}-{bot} x {x0}-{x1}")


if __name__ == "__main__":
    main()
