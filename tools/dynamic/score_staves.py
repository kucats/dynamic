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
and per system the staff list.

System grouping precedence: --index (reviewed bands from
public/score/<id>/index.json) > --score-json (the '//' separator glyph
template embedded in score.json, same mechanism build_score.py used) >
gap heuristic (fallback only — inter-system gaps can be SMALLER than
group gaps inside a system, e.g. pdf p162: 170 px vs 270 px on p4).

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
    """Split staff indices into systems at large vertical gaps (fallback only)."""
    import numpy as np

    if not staves:
        return []
    heights = [s[4] - s[0] for s in staves]
    med = float(np.median(heights))
    systems: list[list[int]] = [[]]
    for i, s in enumerate(staves):
        if systems[-1] and s[0] - staves[i - 1][4] > gap_factor * med:
            systems.append([])
        systems[-1].append(i)
    return systems


def crop_frame(im, dpi: float) -> tuple[float, float, float, float]:
    """Ink-bbox crop window that build_score.page_image applies before resizing
    to the published WebP frame — reproduced on a render of any dpi."""
    import numpy as np

    pad = int(round(40 * dpi / 200.0))          # build_score renders at DPI=200
    ink = np.where(im < 128)
    if len(ink[0]):
        y0 = max(0.0, float(ink[0].min()) - pad)
        y1 = min(float(im.shape[0]), float(ink[0].max()) + pad)
        x0 = max(0.0, float(ink[1].min()) - pad)
        x1 = min(float(im.shape[1]), float(ink[1].max()) + pad)
    else:
        y0, y1, x0, x1 = 0.0, float(im.shape[0]), 0.0, float(im.shape[1])
    return y0, y1, x0, x1


def bands_from_index(index_path: Path, page: int, im, dpi: float) -> list[tuple[float, float]]:
    """Reviewed system bands from public/score/<id>/index.json, in render px.

    index.json y/x values are pixels of the cropped 1600px-wide WebP, not raw
    render pixels: map them back fractionally through this render's own crop."""
    idx = json.loads(index_path.read_text(encoding="utf-8"))
    pg = next(p for p in idx["pages"] if p["pdf"] == page)
    y0, y1, _, _ = crop_frame(im, dpi)
    k = (y1 - y0) / pg["h"]
    return [(y0 + s["y0"] * k, y0 + s["y1"] * k) for s in pg["systems"]]


def split_at_separators(staves: list[list[float]], seps: list[float]) -> list[list[int]]:
    """Group staff indices into systems cut at the '//' separator marks:
    a new system starts whenever a separator y sits between two adjacent
    staff centres."""
    if not staves:
        return []
    systems: list[list[int]] = [[]]
    prev = None
    for i, s in enumerate(staves):
        c = (s[0] + s[4]) / 2
        if prev is not None and any(prev < y < c for y in seps):
            systems.append([])
        systems[-1].append(i)
        prev = c
    return systems


def separator_marks(im, score_json: Path, dpi: float) -> list[float]:
    """y positions of the '//' system-separator marks via score.json's
    embedded template (captured at build_score's 200 dpi)."""
    import base64

    import cv2
    import numpy as np

    cfg = json.loads(score_json.read_text(encoding="utf-8"))
    uri = cfg.get("separator")
    if not uri:
        return []
    tpl = cv2.imdecode(np.frombuffer(base64.b64decode(uri.split(",", 1)[1]), np.uint8),
                       cv2.IMREAD_GRAYSCALE)
    k = dpi / 200.0
    if abs(k - 1.0) > 0.01:
        tpl = cv2.resize(tpl, None, fx=k, fy=k)
    m = cv2.matchTemplate(im[:, : int(420 * k)], tpl, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(m > 0.6)
    hits: list[list[float]] = []
    for y, x in sorted(zip(ys.tolist(), xs.tolist())):
        if hits and y - hits[-1][0] < 40 * k:
            if m[y, x] > hits[-1][1]:
                hits[-1] = [y, m[y, x]]
        else:
            hits.append([y, m[y, x]])
    return [y + tpl.shape[0] / 2 for y, _ in hits]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("page", type=int)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--work", default=Path("work"), type=Path)
    ap.add_argument("--index", type=Path, help="public/score/<id>/index.json for reviewed system bands")
    ap.add_argument("--score-json", type=Path, help="score.json holding the '//' separator template")
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
        bands = bands_from_index(args.index, args.page, im, args.dpi)
        # Nearest-band assignment: index bands can cut slightly inside the
        # top/bottom staff, so each staff joins the band whose [y0, y1]
        # interval is closest to its centre.
        systems = [[] for _ in bands]
        for i, s in enumerate(ST):
            c = (s[0] + s[4]) / 2
            bi = min(range(len(bands)), key=lambda j: max(0.0, bands[j][0] - c, c - bands[j][1]))
            systems[bi].append(i)
        for bi, g in enumerate(systems):
            if not g:
                print(f"WARNING: index band {bi + 1} captured no staves "
                      "— detection failure or band/render mismatch", file=sys.stderr)
    elif args.score_json:
        systems = split_at_separators(ST, separator_marks(im, args.score_json, args.dpi))
    else:
        systems = group_systems(ST)
        if len(systems) == 1 and len(ST) > 16:
            print("WARNING: gap grouping returned one system of "
                  f"{len(ST)} staves — this layout maxes out at 16, so nearby "
                  "systems were probably merged; supply --index or --score-json",
                  file=sys.stderr)
    systems = [g for g in systems if g]

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
