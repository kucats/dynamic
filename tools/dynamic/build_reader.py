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

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "public/reader/data"
CROP_X = (170, 2790)          # default horizontal crop; per-page crop follows the detected staff extent


def render_page(pdf: Path, page: int, work: Path, dpi: int = 300) -> Path:
    png = work / f"p{page}.png"
    if not png.exists():
        work.mkdir(parents=True, exist_ok=True)
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi), "-png", "-singlefile", "-gray",
                        str(pdf), str(work / f"p{page}")], check=True)
    return png


def staff_extent(im, ST) -> tuple[int, int]:
    """Left/right x of the staff lines (union over systems), padded for clefs and final barlines."""
    import numpy as np

    B = im < 140
    xs0, xs1 = [], []
    for s in ST:
        row = B[int(round(s[0]))] & B[int(round(s[4]))]
        cols = np.where(row)[0]
        if len(cols):
            xs0.append(int(np.percentile(cols, 1)))
            xs1.append(int(np.percentile(cols, 99)))
    if not xs0:
        return CROP_X
    return max(0, min(xs0) - 110), min(im.shape[1], max(xs1) + 40)


def crop_system(im, s: list[float], first: bool, cx: tuple[int, int]):
    import cv2
    import numpy as np

    top = max(0, int(s[0]) - (200 if first else 150))
    bot = min(im.shape[0], int(s[4]) + 100)
    c = im[top:bot, cx[0]:cx[1]].copy()
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


def png_b64(arr) -> str:
    from PIL import Image

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


def conducting(m: dict) -> dict:
    """Meter strings and the optional conducting plan ([bar, beats per bar]) for the reader's conductor."""
    out = dict(meters=m["meters"])
    if m.get("conduct"):
        out["conduct"] = m["conduct"]
    if m.get("conduct_note"):
        out["conduct_note"] = m["conduct_note"]
    return out


def review_items(notes: list[dict], systems: list[dict]) -> list[dict]:
    """Expose unresolved note readings as explicit, non-playable review records."""
    return [
        dict(note_id=n["id"], page=systems[n["s"]]["page"], movement=n["mvt"], bar=n["bar"],
             pitch=n["p"], status="unresolved", detail=n["unc"], playback=False)
        for n in notes if n.get("unc")
    ]


def build(part_dir: Path, pdf: Path, work: Path) -> dict:
    import cv2
    from common import CLARINET_KEYS, HORN_KEYS, TROMBONE_POS, label, label_german, parse_pitch, staves, transpose

    cfg = json.loads((part_dir / "part.json").read_text(encoding="utf-8"))
    pages = sorted({p for m in cfg["movements"] for p in m["pages"]})
    splits = {s["page"]: s for s in cfg.get("splits", [])}
    systems, notes = [], []
    dpi = cfg.get("dpi", 300)
    wdir = work / cfg["id"]
    for page in pages:
        im = cv2.imread(str(render_page(pdf, page, wdir, dpi)), cv2.IMREAD_GRAYSCALE)
        ST = staves(im < 140)
        cx = staff_extent(im, ST)
        data = json.loads((part_dir / f"pages/notes_p{page:02d}.json").read_text(encoding="utf-8"))
        bars = json.loads((part_dir / f"pages/bars_p{page:02d}.json").read_text(encoding="utf-8"))
        mv_here = [m["key"] for m in cfg["movements"] if page in m["pages"]]
        sys_index = {}
        for si, s in enumerate(ST, 1):
            mv = mv_here[0]
            if page in splits and si >= splits[page]["first_system"]:
                mv = splits[page]["movement"]
            crop, top = crop_system(im, s, si == 1, cx)
            segs = [[round(g["xa"] - cx[0]), round(g["xb"] - cx[0]), g.get("label", "")]
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
            rec = dict(s=sy["i"], mvt=sy["mvt"], x=round(n["x"] - cx[0], 1), y=round(n["y"] - sy["top"], 1),
                       bar=n["bar"], off=float(Fraction(n["off"])), dur=float(Fraction(n["dur"])),
                       tie=bool(n.get("tie_from_prev")), unc=n.get("uncertain") or "", old=old, p=n["pitch"],
                       sim=bool(n.get("sim")))
            if cfg.get("instrument") == "trombone":        # non-transposing; German names + slide position
                w_ = label_german(L, a, wo)
                rec.update(key="C", w=w_, f=w_, snd=w_, pos=TROMBONE_POS.get(w_[2]))
            elif cfg.get("instrument") == "clarinet":      # in A / Bb; 'f' = how a Bb clarinet reads it
                key = n.get("cl_key") or cfg.get("default_cl_key", "A")
                dl, ds = CLARINET_KEYS[key]
                s_ = transpose(L, a, wo, dl, ds)
                f_ = transpose(*s_, 1, 2)
                rec.update(key=key, w=label(L, a, wo), f=label(*f_), snd=label(*s_))
            elif cfg.get("instrument") == "viola":         # non-transposing, alto clef, sounds as written
                w_ = label(L, a, wo)
                rec.update(key="C", w=w_, f=w_, snd=w_)
            else:
                key = n.get("horn_key") or cfg.get("default_horn_key", "F")
                dl, ds = HORN_KEYS[key]
                s_ = transpose(L, a, wo, dl, ds)
                f_ = transpose(*s_, 4, 7)
                rec.update(key=key, w=label(L, a, wo), f=label(*f_), snd=label(*s_))
            notes.append(rec)
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
        movements.append(dict(key=m["key"], title=m["title"], short=m.get("short"), last=m["last"], timeline=timeline,
                              notes=sum(1 for n in notes if n["mvt"] == m["key"]), **conducting(m)))
    for s in systems:
        del s["top"]
    out = dict(schema=1, id=cfg["id"], instrument=cfg.get("instrument", "horn"), title=cfg["title"], subtitle=cfg["subtitle"], composer=cfg["composer"],
               work=cfg["work"], part=cfg["part"], source=cfg["source"], status=cfg["status"],
               limitations=cfg["limitations"], pdf=cfg.get("pdf"), movements=movements,
               systems=systems, notes=notes, review_items=review_items(notes, systems))
    return out


def refresh_existing_metadata(part_dir: Path) -> None:
    """Refresh provenance and review metadata without the uncommitted source PDF.

    This is for source-note/status corrections when the generated system crops are
    already present. Full score-image regeneration still requires the source PDF.
    """
    cfg = json.loads((part_dir / "part.json").read_text(encoding="utf-8"))
    data_path = OUT / f"{cfg['id']}.json"
    if not data_path.is_file():
        raise SystemExit(f"{data_path.relative_to(ROOT)} is missing; a full build needs the source PDF")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    if data.get("id") != cfg["id"]:
        raise SystemExit(f"Reader data ID mismatch for {part_dir}")
    source_notes = []
    pages_dir = part_dir / "pages"
    for page in sorted({page for movement in cfg["movements"] for page in movement["pages"]}):
        page_data = json.loads((pages_dir / f"notes_p{page:02d}.json").read_text(encoding="utf-8"))
        source_notes.extend((page, note) for note in page_data["notes"])
    if len(source_notes) != len(data["notes"]):
        raise SystemExit(f"Note count mismatch for {cfg['id']}: source={len(source_notes)} reader={len(data['notes'])}")
    for reader_note, (page, source_note) in zip(data["notes"], source_notes):
        if (reader_note["p"] != source_note["pitch"] or reader_note["bar"] != source_note["bar"]
                or data["systems"][reader_note["s"]]["page"] != page):
            raise SystemExit(f"Source/reader note mismatch at note {reader_note['id']} in {cfg['id']}")
        reader_note["unc"] = source_note.get("uncertain") or ""
    data["source"] = cfg["source"]
    data["status"] = cfg["status"]
    data["limitations"] = cfg["limitations"]
    data["pdf"] = cfg.get("pdf")
    for movement in data["movements"]:
        source = next((m for m in cfg["movements"] if m["key"] == movement["key"]), None)
        if source and source.get("short"):
            movement["short"] = source["short"]
        if source:
            for key in ("meters", "conduct", "conduct_note"):
                movement.pop(key, None)
            movement.update(conducting(source))
    data["review_items"] = review_items(data["notes"], data["systems"])
    data_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    idx_path = ROOT / "public/reader/parts.json"
    index = json.loads(idx_path.read_text(encoding="utf-8"))
    entry = next((p for p in index["parts"] if p["id"] == cfg["id"]), None)
    if entry is None:
        raise SystemExit(f"{cfg['id']} is missing from {idx_path.relative_to(ROOT)}")
    entry.update(id=data["id"], title=data["title"], subtitle=data["subtitle"], part=data["part"],
                 work=data["work"], composer=data["composer"], status=data["status"], pdf=data["pdf"],
                 movements=[dict(key=m["key"], title=m["title"], short=m.get("short"), notes=m["notes"])
                            for m in data["movements"]], notes=len(data["notes"]),
                 data=f"reader/data/{data['id']}.json")
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"refreshed metadata for {cfg['id']}: {len(data['review_items'])} unresolved note(s)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path)
    ap.add_argument("--work", default=Path("work"), type=Path)
    ap.add_argument("--refresh-metadata", action="store_true",
                    help="refresh source/status/review JSON without rerendering system images from the source PDF")
    ap.add_argument("parts", nargs="*", type=Path)
    args = ap.parse_args()
    if args.refresh_metadata:
        if not args.parts:
            ap.error("--refresh-metadata requires one or more part directories")
        for part_dir in args.parts:
            refresh_existing_metadata(part_dir)
        return
    if args.pdf is None:
        ap.error("--pdf is required unless --refresh-metadata is used")
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
                                 movements=[dict(key=m["key"], title=m["title"], short=m.get("short"), notes=m["notes"])
                                            for m in data["movements"]],
                          notes=len(data["notes"]), data=f"reader/data/{data['id']}.json"))
        print(f"built {data['id']}: {len(data['notes'])} notes, {len(data['systems'])} systems")
    idx_path = ROOT / "public/reader/parts.json"
    merged = json.loads(idx_path.read_text(encoding="utf-8"))["parts"] if idx_path.exists() else []
    for entry in index:                     # replace in place, append new parts at the end
        pos = next((k for k, p in enumerate(merged) if p["id"] == entry["id"]), None)
        if pos is None:
            merged.append(entry)
        else:
            merged[pos] = entry
    idx_path.write_text(json.dumps(dict(schema=1, parts=merged), ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")


if __name__ == "__main__":
    main()
