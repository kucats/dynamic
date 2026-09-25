#!/usr/bin/env python3
"""Detect every 5-line staff on a full-score page and group them into systems.

Part pages carry one staff per row ("sys" = the row); a full-score page carries
~15 staves per system and the Bartoš critical edition prints the winds, brass
and strings choirs as three bracketed groups.  The same pipeline step works —
only the spacing range differs (score staves are ~17.6 px apart at 300 dpi,
so render at --dpi 600 for ~35 px spacing, matching part pages at 300 dpi).

Usage:
  python3 tools/dynamic/score_staves.py 4 --dpi 600 \
      --index public/score/dvorak8/index.json --work work

Reads work/p<PAGE>.png (300 dpi) or work/p<PAGE>_d<DPI>.png for other --dpi
values (render with pymupdf/pdftoppm first).  Writes
work/score_staves_p<PAGE>.json: per staff {sys, row, y, spacing, gap_above}
and per system the staff list.  With --index the reviewed system bands of the
full-score viewer are used for grouping; otherwise a gap threshold.

Tacet staves are omitted by the engraver (e.g. pdf p16 system 1 = 6 staves),
so staff->instrument assignment is NOT fixed: read each system's left margin.
--names writes work/score_names_p<PAGE>_s<SYS>.png crops for that purpose.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def detect_staves(B, lo: float = 10.0, hi: float = 40.0, cover: float = 0.55):
    """All 5-line staves on a boolean (dark=True) page image at any dpi.

    Horizontal coverage `cover` over 1/5-page slices; line spacing between
    `lo` and `hi` px.  Returns a list of 5 y-values (top..bottom), sorted.
    """
    import numpy as np

    H, W = B.shape
    step = max(80, int(W * 0.02))          # grouping tolerance for line thickness
    win = max(200, int(W * 0.10))          # slice width ~10% of page width
    allst: list[list[float]] = []
    for x0 in range(int(W * 0.20), int(W * 0.80), max(200, int(W * 0.13))):
        rows = B[:, x0:x0 + win].sum(1)
        cand = [y for y in range(H) if rows[y] > cover * win]
        g: list[list[int]] = []
        for y in cand:
            if g and y - g[-1][-1] <= max(2, step // 6):
                g[-1].append(y)
            else:
                g.append([y])
        ys = [sum(q) / len(q) for q in g]
        i = 0
        while i + 4 < len(ys):
            s = ys[i:i + 5]
            d = np.diff(s)
            if d.max() - d.min() < max(5.0, hi * 0.3) and lo < d.mean() < hi:
                allst.append(s)
                i += 5
            else:
                i += 1
    allst.sort(key=lambda s: s[0])
    merged: list[list[list[float]]] = []
    for s in allst:
        if merged and abs(merged[-1][0][0] - s[0]) < 3 * hi:
            merged[-1].append(s)
        else:
            merged.append([s])
    return [list(np.mean(np.array(grp), axis=0)) for grp in merged]


def group_systems(staves: list[list[float]], gap_factor: float = 4.0) -> list[list[int]]:
    """Split staff indices into systems at large vertical gaps."""
    import numpy as np

    heights = [s[4] - s[0] for s in staves]
    med = float(np.median(heights)) if heights else 1.0
    systems: list[list[int]] = [[]]
    for i, s in enumerate(staves):
        if systems[-1] and s[0] - staves[i - 1][4] > gap_factor * med:
            systems.append([])
        systems[-1].append(i)
    return systems


def bands_from_index(index_path: Path, page: int, scale: float) -> list[tuple[float, float]]:
    """Reviewed system bands from public/score/<id>/index.json, scaled to render px."""
    idx = json.loads(index_path.read_text(encoding="utf-8"))
    pg = next(p for p in idx["pages"] if p["pdf"] == page)
    w = idx.get("width") or pg.get("w") or 1600
    k = scale / w
    return [(s["y0"] * k, s["y1"] * k) for s in pg["systems"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("page", type=int)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--work", default=Path("work"), type=Path)
    ap.add_argument("--index", type=Path, help="public/score/<id>/index.json for reviewed system bands")
    ap.add_argument("--lo", type=float, default=None, help="min staff-line spacing px (default 10 @300dpi, scaled)")
    ap.add_argument("--hi", type=float, default=None, help="max staff-line spacing px (default 40 @300dpi, scaled)")
    ap.add_argument("--names", action="store_true", help="crop left-margin name strips to work/score_names_*")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    png = args.work / (f"p{args.page}_d{args.dpi}.png" if args.dpi != 300 else f"p{args.page}.png")
    if not png.is_file():
        raise SystemExit(f"{png} not found; render the score page at {args.dpi} dpi first")
    im = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    B = im < 140
    k = args.dpi / 300.0
    lo = args.lo if args.lo is not None else 10.0 * k
    hi = args.hi if args.hi is not None else 40.0 * k
    ST = detect_staves(B, lo=lo, hi=hi)
    spacings = [(s[4] - s[0]) / 4 for s in ST]
    if spacings and float(np.median(spacings)) < lo:
        raise SystemExit(f"median staff spacing {np.median(spacings):.1f}px < lo={lo:.1f}px "
                         f"— {png.name} was probably rendered at a different dpi")

    if args.index:
        bands = bands_from_index(args.index, args.page, im.shape[1])
        # Nearest-band assignment: index bands can cut slightly inside the
        # top/bottom staff (p16 sys2 excludes Fl.I), so each staff joins the
        # band whose [y0, y1] interval is closest to its centre.
        systems = [[] for _ in bands]
        for i, s in enumerate(ST):
            c = (s[0] + s[4]) / 2
            bi = min(range(len(bands)), key=lambda j: max(0.0, bands[j][0] - c, c - bands[j][1]))
            systems[bi].append(i)
        systems = [g for g in systems if g]
    else:
        systems = group_systems(ST)

    rec = {"page": args.page, "dpi": args.dpi, "image": str(png),
           "staff_count": len(ST), "systems": len(systems),
           "staves": [{"i": i + 1, "sys": si + 1, "row": ri + 1,
                       "y": [round(v, 1) for v in ST[i]],
                       "spacing": round((ST[i][4] - ST[i][0]) / 4, 1),
                       "gap_above": round(ST[i][0] - ST[i - 1][4], 1) if i else 0.0,
                       "instrument": None}
                      for si, inds in enumerate(systems) for ri, i in enumerate(inds)]}
    out = args.out or args.work / f"score_staves_p{args.page}.json"
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.names:
        for si, inds in enumerate(systems):
            y0 = int(ST[inds[0]][0])
            y1 = int(ST[inds[-1]][4])
            crop = im[max(0, y0 - int(30 * k)):min(im.shape[0], y1 + int(30 * k)), 0:int(im.shape[1] * 0.16)]
            cv2.imwrite(str(args.work / f"score_names_p{args.page}_s{si + 1}.png"), crop)

    for r in rec["staves"]:
        print(f"staff {r['i']:>2}  sys {r['sys']} row {r['row']:>2}  y {r['y'][0]:>7.0f}-{r['y'][4]:<7.0f}  "
              f"spacing {r['spacing']:>4}  gap+{r['gap_above']:>6.0f}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
