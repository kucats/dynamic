#!/usr/bin/env python3
"""Build per-part and per-work bar-number indexes.

Answers "where is bar 120?" for every decoded part and (when a score index
exists) for the conductor's score, without loading note data.

Outputs:
  project/<composer>/<work>/<part>/dynamic/bar-index.json
      {"schema":1, "id": <part id>, "bars": [[bar, page], ...]}  (sorted)
  project/<composer>/<work>/bar-map.json
      {"schema":1, "work": <work>, "parts": {id: {"title":..., "bars":[[bar,page]...]}},
       "score": {"pages": [{"pdf":p,"printed":n,"mvt":m,"bars":[first,last]}...]} or absent}

Run:  python3 tools/dynamic/bar_index.py <composer>/<work>
  e.g. python3 tools/dynamic/bar_index.py dvorak/symphony-no-8
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def page_bars(page_file: Path):
    """Bar numbers present on one notes page, tolerating schema variants:
    meta.bars as [lo, hi] | {mvt: [lo, hi]} | absent (then use note 'bar' fields).
    Returns a flat sorted list of unique bar ints (movement-qualified bars are
    merged; parts whose bars restart per movement still index by printed bar).
    """
    d = json.loads(page_file.read_text())
    bars = set()
    mb = d.get("meta", {}).get("bars")
    if isinstance(mb, list) and len(mb) == 2:
        lo, hi = mb
        if isinstance(lo, int) and isinstance(hi, int):
            bars.update(range(lo, hi + 1))
    elif isinstance(mb, dict):
        for rng in mb.values():
            if isinstance(rng, list) and len(rng) == 2:
                lo, hi = rng
                if isinstance(lo, int) and isinstance(hi, int):
                    bars.update(range(lo, hi + 1))
    if not bars:
        for n in d.get("notes", []):
            b = n.get("bar") or n.get("page_local_bar")
            if isinstance(b, int):
                bars.add(b)
    return sorted(bars)


def part_index(part_dir: Path):
    """Return (part_id, title, [[bar, page], ...]) for one <part>/dynamic dir."""
    pj = part_dir / "part.json"
    if not pj.exists():
        return None
    meta = json.loads(pj.read_text())
    pages = {}
    for nf in sorted((part_dir / "pages").glob("notes_p*.json")):
        page = int(re.search(r"notes_p(\d+)", nf.name).group(1))
        for b in page_bars(nf):
            pages.setdefault(b, page)  # first page wins for repeated bars
    return meta.get("id") or part_dir.name, meta.get("title") or part_dir.name, sorted(pages.items())


def score_pages(score_id: str):
    idx = ROOT / "public" / "score" / score_id / "index.json"
    if not idx.exists():
        return None
    d = json.loads(idx.read_text())
    out = []
    for pg in d.get("pages", []):
        nums = [b[2] for s in pg.get("systems", []) for b in s.get("bars", [])]
        if nums:
            out.append({"pdf": pg["pdf"], "printed": pg.get("printed"), "mvt": pg.get("mvt"),
                        "bars": [min(nums), max(nums)]})
    return out


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    work_rel = sys.argv[1]
    work_dir = ROOT / "project" / work_rel
    if not work_dir.is_dir():
        sys.exit(f"no such work dir: {work_dir}")
    parts = {}
    for part_dir in sorted(work_dir.iterdir()):
        dyn = part_dir / "dynamic"
        if not dyn.is_dir():
            continue
        got = part_index(dyn)
        if not got:
            continue
        pid, title, bars = got
        if not bars:
            continue
        (dyn / "bar-index.json").write_text(
            json.dumps({"schema": 1, "id": pid, "bars": [[b, p] for b, p in bars]},
                       ensure_ascii=False))
        parts[pid] = {"title": title, "bars": [[b, p] for b, p in bars]}
    # a score index exists only for works with public/score/<id>
    score = None
    for cand in {work_dir.name.replace("symphony-no-", ""), work_rel.split("/")[-1],
                 "dvorak8" if "dvorak" in work_rel else work_dir.name}:
        score = score_pages(cand)
        if score:
            break
    out = {"schema": 1, "work": work_rel, "parts": parts}
    if score:
        out["score"] = {"pages": score}
    (work_dir / "bar-map.json").write_text(json.dumps(out, ensure_ascii=False))
    print(f"{work_rel}: {len(parts)} parts indexed"
          + (f", score {len(score)} pages" if score else ", no score index"))


if __name__ == "__main__":
    main()
