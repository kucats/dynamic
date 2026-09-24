#!/usr/bin/env python3
"""Build the lazy-loaded full-score viewer data (public/score/<id>/) from a user-supplied score PDF.

Inputs (committed):
  project/<composer>/<work>/full-score/score.json   movement page ranges, printed-page offset, reviewed
                                                    per-page barline overrides
Input (NOT committed): the source score PDF, checked against score.json's SHA-256.

Pipeline per page: render 200 dpi grayscale -> deskew (maximise vertical projection) -> detect barlines as
long vertical strokes, split systems at the printed '//' separators (template match), keep strokes covering >= 30 % of the system height ->
apply the reviewed overrides -> number bars per movement -> crop margins, resize, save WebP.

Only bar numbers are derived; no notes are read. Detection output is a candidate until the review sheets
(--review) have been compared with the printed bar numbers (every 5 bars in the Bartoš edition) and the
disagreements have been recorded as overrides in score.json.

Usage:
  python3 tools/dynamic/build_score.py --pdf /path/to/score.pdf [--work work] [--review work/review] [score_dir]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DPI = 200
OUT_W = 1600          # published image width (px)
WEBP_Q = 50


# ---------- rendering ----------
def render(pdf: Path, page: int, work: Path) -> Path:
    png = work / f"p{page:03d}.png"
    if png.exists():
        return png
    work.mkdir(parents=True, exist_ok=True)
    try:
        import pymupdf  # optional; faster than poppler for large 1-bit scans
        doc = pymupdf.open(pdf)
        doc[page - 1].get_pixmap(dpi=DPI, colorspace="gray").save(png)
    except ImportError:
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(DPI), "-png", "-singlefile",
                        "-gray", str(pdf), str(png.with_suffix(""))], check=True)
    return png


def deskew(im: np.ndarray) -> tuple[np.ndarray, float]:
    B = (im < 170).astype(np.float32)
    Bs = cv2.resize(B, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    h, w = Bs.shape
    best = (0.0, -1.0)
    for a in np.arange(-0.8, 0.801, 0.02):
        r = cv2.warpAffine(Bs, cv2.getRotationMatrix2D((w / 2, h / 2), a, 1), (w, h))
        v = float((r.sum(0) ** 2).sum())
        if v > best[1]:
            best = (float(a), v)
    H, W = im.shape
    M = cv2.getRotationMatrix2D((W / 2, H / 2), best[0], 1)
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=255), best[0]


# ---------- detection ----------
def _segments(im: np.ndarray, kh: int = 150):
    B = (im < 170).astype(np.uint8)
    Bd = cv2.dilate(B, np.ones((1, 3), np.uint8))           # tolerate residual slant
    V = cv2.morphologyEx(Bd, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, kh)))
    _n, _lab, st, _ = cv2.connectedComponentsWithStats(V, 8)
    return sorted((x + w / 2, y, y + h) for x, y, w, h, _a in st[1:] if w <= 10)


def _cluster(vals, tol):
    out: list[list[float]] = []
    for v in sorted(vals):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return out


def separators(im: np.ndarray, tpl: np.ndarray | None, thr: float = 0.6) -> list[int]:
    """y positions of the '//' system-separator marks in the left margin."""
    if tpl is None:
        return []
    m = cv2.matchTemplate(im[:, :420], tpl, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(m > thr)
    hits: list[list[float]] = []
    for y, x in sorted(zip(ys, xs)):
        if hits and y - hits[-1][0] < 40:
            if m[y, x] > hits[-1][1]:
                hits[-1] = [y, m[y, x]]
        else:
            hits.append([y, m[y, x]])
    return [int(y) + tpl.shape[0] // 2 for y, _ in hits]


def detect(im: np.ndarray, seps: list[int]) -> list[dict]:
    """Return systems [{y0, y1, bl: [x, ...]}]; systems are the bands between '//' separators."""
    H = im.shape[0]
    edges = [0] + sorted(seps) + [H]
    segs = _segments(im)
    out = []
    for b0, b1 in zip(edges, edges[1:]):
        groups: list[dict] = []
        for s in sorted((s for s in segs if b0 <= (s[1] + s[2]) / 2 < b1), key=lambda s: s[1]):
            if groups and s[1] <= groups[-1]["y1"] - 30:
                g = groups[-1]
                g["y1"] = max(g["y1"], s[2])
                g["s"].append(s)
            else:
                groups.append(dict(y0=s[1], y1=s[2], s=[s]))
        if not groups:
            continue
        for g in groups:
            g["xs"] = [float(np.mean(c)) for c in _cluster([s[0] for s in g["s"]], 6)]
        shift = 0.0                        # residual skew between groups of one system
        for p, g in zip(groups, groups[1:]):
            cands = [a - b for a in g["xs"] for b in p["xs"] if abs(a - b) <= 25] or [0]
            sh = max(cands, key=lambda d: sum(any(abs(x - d - y) <= 4 for y in p["xs"]) for x in g["xs"]))
            shift += sh
            g["shift"] = shift
        pts = sorted((s[0] - g.get("shift", 0), s[1], s[2]) for g in groups for s in g["s"])
        Y0, Y1 = int(min(g["y0"] for g in groups)), int(max(g["y1"] for g in groups))
        cl: list[list[tuple]] = []
        for p in pts:
            if cl and p[0] - cl[-1][-1][0] <= 10:
                cl[-1].append(p)
            else:
                cl.append([p])
        xs = []
        for c in cl:                        # keep strokes that cover enough of the system height
            cov, cur = 0, None
            for a, b in sorted((a, b) for _, a, b in c):
                if cur and a <= cur[1]:
                    cur[1] = max(cur[1], b)
                else:
                    if cur:
                        cov += cur[1] - cur[0]
                    cur = [a, b]
            cov += cur[1] - cur[0]
            if cov >= 0.3 * max(1, Y1 - Y0):
                xs.append(float(np.mean([q[0] for q in c])))
        Hm = cv2.morphologyEx((im[Y0:Y1] < 170).astype(np.uint8), cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1)))
        col = Hm.sum(0)
        med = float(np.median(col[col > 0])) if (col > 0).any() else 0
        if med and xs:                      # staff start / end lines that were not long enough
            left = int(np.argmax(col >= 0.5 * med))
            right = int(len(col) - 1 - np.argmax(col[::-1] >= 0.5 * med))
            if xs[0] - left > 60:
                xs = [float(left)] + xs
            if right - xs[-1] > 60:
                xs = xs + [float(right)]
        bl = [round(float(np.mean(c)), 1) for c in _cluster(xs, 28)]   # double / repeat barlines
        if len(bl) >= 2:
            out.append(dict(y0=Y0, y1=Y1, bl=bl))
    return out


def apply_overrides(systems: list[dict], ov: dict | None) -> list[dict]:
    """Overrides (reviewed against printed bar numbers):
       systems: [[x, ...], ...]      replace all barlines (y ranges kept, or given via "y")
       merge: true                   treat the page as one system (first system's barlines)
       drop_system: [i, ...]         discard detected fragments
       add: [[i, x], ...] / drop: [[i, x], ...]   add or remove one barline in system i
    """
    if not ov:
        return systems
    systems = [dict(s, bl=list(s["bl"])) for s in systems]
    if ov.get("merge"):
        systems = [dict(y0=min(s["y0"] for s in systems), y1=max(s["y1"] for s in systems), bl=systems[0]["bl"])]
    if ov.get("drop_system"):
        systems = [s for i, s in enumerate(systems) if i not in set(ov["drop_system"])]
    for i, x in ov.get("drop", []):
        bl = systems[i]["bl"]
        k = min(range(len(bl)), key=lambda j: abs(bl[j] - x))
        if abs(bl[k] - x) > 20:
            raise SystemExit(f"override drop {x} not found in system {i}: {bl}")
        del bl[k]
    for i, x in ov.get("add", []):
        systems[i]["bl"] = sorted(systems[i]["bl"] + [float(x)])
    if "systems" in ov:
        ys = ov.get("y") or [[s["y0"], s["y1"]] for s in systems]
        systems = [dict(y0=y[0], y1=y[1], bl=[float(v) for v in bl]) for y, bl in zip(ys, ov["systems"])]
    return systems


def analyse(args):
    pdf, page, work, tpl_path = args
    im, ang = deskew(cv2.imread(str(render(pdf, page, work)), cv2.IMREAD_GRAYSCALE))
    cv2.imwrite(str(work / f"d{page:03d}.png"), im)
    tpl = None
    if tpl_path:                            # 50x50 crop of the printed '//' glyph, embedded as a data URI
        raw = base64.b64decode(tpl_path.split(",", 1)[1])
        tpl = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
    return page, ang, detect(im, separators(im, tpl))


# ---------- output ----------
def page_image(work: Path, page: int, out: Path) -> tuple[float, int, int, int, int]:
    im = cv2.imread(str(work / f"d{page:03d}.png"), cv2.IMREAD_GRAYSCALE)
    ink = np.where(im < 128)
    if len(ink[0]):
        y0, y1 = max(0, ink[0].min() - 40), min(im.shape[0], ink[0].max() + 40)
        x0, x1 = max(0, ink[1].min() - 40), min(im.shape[1], ink[1].max() + 40)
    else:
        y0, y1, x0, x1 = 0, im.shape[0], 0, im.shape[1]
    crop = im[y0:y1, x0:x1]
    scale = min(1.0, OUT_W / crop.shape[1])
    img = Image.fromarray(crop).resize((round(crop.shape[1] * scale), round(crop.shape[0] * scale)), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "WEBP", quality=WEBP_Q, method=6)
    return scale, x0, y0, img.width, img.height


def review_sheet(work: Path, pages: list[dict], path: Path) -> None:
    """Top strips of every system with detected barlines (red) and assigned numbers (blue)."""
    rows = []
    for pg in pages:
        im = cv2.imread(str(work / f"d{pg['pdf']:03d}.png"), cv2.IMREAD_GRAYSCALE)
        for sy in pg["raw"]:
            y0 = max(0, int(sy["y0"]) - 90)
            c = cv2.cvtColor(im[y0:int(sy["y0"]) + 30], cv2.COLOR_GRAY2BGR)
            c = np.vstack([c, np.full((40, c.shape[1], 3), 255, np.uint8)])
            for x in sy["bl"]:
                cv2.line(c, (int(x), 60), (int(x), c.shape[0]), (0, 0, 255), 2)
            for x, b in zip(sy["bl"], sy["labels"]):
                cv2.putText(c, str(b), (int(x) + 6, c.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2)
            cv2.putText(c, f"p{pg['pdf']} {pg['mvt']}", (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 140, 0), 2)
            rows.append(cv2.resize(c, None, fx=0.6, fy=0.6, interpolation=cv2.INTER_AREA))
    if rows:
        w = max(r.shape[1] for r in rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), np.vstack([np.pad(r, ((0, 4), (0, w - r.shape[1]), (0, 0)), constant_values=128)
                                          for r in rows]))


def build(score_dir: Path, pdf: Path, work: Path, review: Path | None) -> dict:
    cfg = json.loads((score_dir / "score.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != cfg["source"]["sha256"]:
        raise SystemExit(f"{score_dir}: source PDF hash mismatch ({digest})")
    wdir = work / cfg["id"]
    wdir.mkdir(parents=True, exist_ok=True)
    tpl = cfg.get("separator")
    pages_n = [p for m in cfg["movements"] for p in range(m["first_page"], m["last_page"] + 1)]
    with ProcessPoolExecutor() as ex:
        found = {p: (a, s) for p, a, s in ex.map(analyse, [(pdf, p, wdir, tpl) for p in pages_n])}
    out_dir = ROOT / "public/score" / cfg["id"]
    pages, bars_per_mvt = [], {}
    for m in cfg["movements"]:
        bar = m.get("first_bar", 1) - 1
        for p in range(m["first_page"], m["last_page"] + 1):
            systems = apply_overrides(found[p][1], cfg.get("overrides", {}).get(str(p)))
            for sy in systems:
                sy["labels"] = []
                for _ in sy["bl"][:-1]:
                    bar += 1
                    sy["labels"].append(bar)
            pages.append(dict(pdf=p, mvt=m["key"], raw=systems, angle=found[p][0]))
        bars_per_mvt[m["key"]] = bar
        if m.get("last_bar") and bar != m["last_bar"]:
            print(f"WARNING: movement {m['key']} numbered to {bar}, expected {m['last_bar']}")
    if review:
        for k in range(0, len(pages), 14):
            review_sheet(wdir, pages[k:k + 14], review / f"review_{pages[k]['pdf']:03d}.png")
    index_pages = []
    for pg in pages:
        rel = f"pages/p{pg['pdf']:03d}.webp"
        scale, x0, y0, w, h = page_image(wdir, pg["pdf"], out_dir / rel)
        X = lambda v: round((v - x0) * scale, 1)
        Y = lambda v: round((v - y0) * scale, 1)
        systems = []
        for sy in pg["raw"]:
            bars = [[X(a), X(b), lab] for a, b, lab in zip(sy["bl"], sy["bl"][1:], sy["labels"])]
            systems.append(dict(y0=max(0, Y(sy["y0"])), y1=min(h, Y(sy["y1"])), bars=bars))
        ver = hashlib.sha256((out_dir / rel).read_bytes()).hexdigest()[:10]     # cache-busting for the SW
        index_pages.append(dict(pdf=pg["pdf"], printed=pg["pdf"] + cfg.get("printed_page_offset", 0), mvt=pg["mvt"],
                                img=f"{rel}?v={ver}", w=w, h=h, systems=systems))
    data = dict(schema=1, id=cfg["id"], title=cfg["title"], composer=cfg["composer"], work=cfg["work"],
                edition=cfg["edition"], source=cfg["source"], status=cfg["status"], limitations=cfg["limitations"],
                movements=[dict(key=m["key"], title=m["title"], last=bars_per_mvt[m["key"]]) for m in cfg["movements"]],
                pages=index_pages)
    (out_dir / "index.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
                                        encoding="utf-8")
    print(f"built score {cfg['id']}: {len(index_pages)} pages, bars {bars_per_mvt}")
    return data


def update_catalog(data: dict) -> None:
    path = ROOT / "public/score/index.json"
    cur = json.loads(path.read_text(encoding="utf-8"))["scores"] if path.exists() else []
    entry = dict(id=data["id"], title=data["title"], composer=data["composer"], work=data["work"],
                 index=f"score/{data['id']}/index.json")
    cur = [e for e in cur if e["id"] != entry["id"]] + [entry]
    path.write_text(json.dumps(dict(schema=1, scores=cur), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--work", default=Path("work"), type=Path)
    ap.add_argument("--review", type=Path, help="write barline review sheets here (not committed)")
    ap.add_argument("score_dir", nargs="?", type=Path, default=ROOT / "project/dvorak/symphony-no-8/full-score")
    args = ap.parse_args()
    update_catalog(build(args.score_dir, args.pdf, args.work.resolve(), args.review))


if __name__ == "__main__":
    sys.exit(main())
