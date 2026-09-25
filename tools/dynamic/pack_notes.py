#!/usr/bin/env python3
"""Pack reader/score note data into a lightweight delivery layout.

Input: a reader data JSON (`public/reader/data/<id>.json`) or any JSON with
`systems[]` (each carrying an `img` data-URI) and `notes[]` objects.

Output layout under --out:
  manifest.json          metadata + dictionaries + system descriptors (no notes, no pixels)
  notes/<shard>.json     packed note rows, one file per shard
  img/<sys>.<ext>        decoded system images, referenced from the manifest

Packing: notes become row arrays over shared dictionaries instead of objects.
Flags bitfield: 1=tie 2=old 4=sim 8=unc-set. `off` is quantised to 1/16 of a
beat. Pitch triples (`w`,`f`,`snd` = [letter, octave, position]) share one
dictionary; `p`, `key`, `mvt`, `unc` get their own. `id` is the row index.

Sharding:
  --shard system   one notes file per system   (part reader: load visible system)
  --shard page     one notes file per page     (score: load the open page only)
  --shard all      single notes file           (whole part in one fetch)

Images: cleaned line-art is near-bimodal, so bilevel wins — measured ~31%
of grayscale PNG as 1-bit WebP-lossless (lossy WebP is strictly worse on
this content). `--img webp` (default) writes 1-bit WebP-lossless when
Pillow is available, `--img png` writes 1-bit PNG, `--img raw` keeps the
source bytes.

Usage:
  python3 pack_notes.py public/reader/data/dvorak8-trombone1.json \
      --out work/pack/trombone1 --shard system
"""

import argparse
import base64
import json
import sys
from pathlib import Path


def put(d, v):
    i = d.get(v)
    if i is None:
        i = len(d["list"])
        d["list"].append(v)
        d[v] = i
    return i


def pack(data, shard_mode):
    dicts = {k: {"list": []} for k in
             ("mvt", "dur", "off", "p", "trip", "key", "pos", "unc")}
    rows = []
    for n in data.get("notes", []):
        flags = (
            (1 if n.get("tie") else 0)
            | (2 if n.get("old") else 0)
            | (4 if n.get("sim") else 0)
            | (8 if n.get("unc") else 0)
        )
        row = [
            n["s"], put(dicts["mvt"], n["mvt"]), n["bar"], n["x"], n["y"],
            put(dicts["dur"], n["dur"]), put(dicts["off"], n.get("off", 0)),
            flags, put(dicts["p"], n["p"]),
            put(dicts["trip"], json.dumps(n.get("w"), separators=(",", ":"), ensure_ascii=False)),
            put(dicts["trip"], json.dumps(n.get("f"), separators=(",", ":"), ensure_ascii=False)),
            put(dicts["trip"], json.dumps(n.get("snd"), separators=(",", ":"), ensure_ascii=False)),
            put(dicts["key"], n.get("key", "")), put(dicts["pos"], n.get("pos")),
            put(dicts["unc"], n.get("unc", "")),
        ]
        rows.append(row)
    return dicts, rows


def shard_key(system, note_s, shard_mode):
    if shard_mode == "page":
        return f"p{system['page']:03d}"
    if shard_mode == "system":
        return f"s{note_s:03d}"
    return "all"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("data", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--shard", choices=["system", "page", "all"], default="system")
    ap.add_argument("--img", choices=["webp", "png", "raw"], default="webp")
    ap.add_argument("--threshold", type=int, default=200)
    a = ap.parse_args()

    try:
        import io
        from PIL import Image
        have_pil = True
    except ImportError:
        have_pil = False

    data = json.loads(a.data.read_text(encoding="utf-8"))
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "notes").mkdir(exist_ok=True)
    (a.out / "img").mkdir(exist_ok=True)

    systems, img_bytes = [], 0
    for s in data.get("systems", []):
        s = dict(s)
        img = s.pop("img", "")
        if img.startswith("data:"):
            head, b64 = img.split(",", 1)
            ext = "png" if "png" in head else "webp" if "webp" in head else "bin"
            name = f"{s.get('i', len(systems)):03d}.{ext}"
            blob = base64.b64decode(b64)
            if have_pil and a.img != "raw":
                im = Image.open(io.BytesIO(blob)).convert("L")
                bw = im.point(lambda v: 255 if v >= a.threshold else 0, "1")
                buf = io.BytesIO()
                if a.img == "webp":
                    bw.convert("L").save(buf, "WEBP", lossless=True)
                    name = name.rsplit(".", 1)[0] + ".webp"
                else:
                    bw.save(buf, "PNG", optimize=True)
                    name = name.rsplit(".", 1)[0] + ".png"
                blob = buf.getvalue()
            img_bytes += len(blob)
            (a.out / "img" / name).write_bytes(blob)
            s["img"] = f"img/{name}"
        systems.append(s)

    dicts, rows = pack(data, a.shard)
    shards = {}
    for r in rows:
        sys_i = r[0]
        sk = shard_key(systems[sys_i], sys_i, a.shard)
        shards.setdefault(sk, []).append(r)

    manifest = {k: v for k, v in data.items() if k not in ("systems", "notes")}
    manifest["schema"] = "notes-packed-1"
    manifest["systems"] = systems
    manifest["dicts"] = {
        k: [json.loads(t) if k == "trip" else t for t in d["list"]]
        for k, d in dicts.items()
    }
    manifest["cols"] = ["s", "mvt", "bar", "x", "y", "dur", "off", "flags",
                        "p", "w", "f", "snd", "key", "pos", "unc"]
    manifest["notes_shards"] = {k: f"notes/{k}.json" for k in sorted(shards)}
    manifest["note_count"] = len(rows)

    mpath = a.out / "manifest.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
                     encoding="utf-8")
    for k, rws in shards.items():
        (a.out / "notes" / f"{k}.json").write_text(
            json.dumps(rws, separators=(",", ":")), encoding="utf-8")

    src = a.data.stat().st_size
    man = mpath.stat().st_size
    nb = sum(p.stat().st_size for p in (a.out / "notes").iterdir())
    cold = man + min((p.stat().st_size for p in (a.out / "notes").iterdir()), default=0)
    print(f"source            {src/1024:9.1f} KB")
    print(f"manifest          {man/1024:9.1f} KB")
    print(f"notes shards      {nb/1024:9.1f} KB  ({len(shards)} files, "
          f"{len(rows)} events, {nb/max(len(rows),1):.1f} B/event)")
    print(f"images (decoded)  {img_bytes/1024:9.1f} KB  ({len(systems)} files)")
    print(f"first-load (m+1n+1i) {(cold + min(img_bytes/len(systems),0) if systems else cold)/1024:9.1f} KB"
          f"  vs {src/1024:.1f} KB monolith")
    return 0


if __name__ == "__main__":
    sys.exit(main())
