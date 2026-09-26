#!/usr/bin/env python3
"""Draft work/bars_auto_pNN.json for a page: detect barlines per staff, segment the
systems, and pre-fill labels by counting the page's note bar numbers.

Usage: python3 tools/dynamic/make_bars_auto.py PAGE [PAGE...]
Reads work/pPAGE.png and work/final_pPAGE.json; writes work/bars_auto_pPAGE.json.
The result is a DRAFT — stems are often detected as barlines and multi-bar rests
need manual labels; fix it into work/bars_pPAGE.json per prompts/03.
"""
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barlines import assign_bars, barlines, is_multirest
from common import staves


def run(p: int) -> None:
    im = cv2.imread(f"work/p{p}.png", 0)
    B = im < 140
    ST = staves(B)
    fin = json.load(open(f"work/final_p{p}.json"))
    notes = fin.get("notes", [])
    meta = fin.get("meta", {})
    bars_range = meta.get("bars", [None, None])
    if isinstance(bars_range, dict):
        first_bar = min(v[0] for v in bars_range.values())
        last_bar = max(v[1] for v in bars_range.values())
    else:
        first_bar, last_bar = bars_range
    out = {}
    prev_last = None
    for si, s in enumerate(ST, 1):
        sys_notes = [n for n in notes if n.get("sys") == si]
        note_xs = [n["x"] for n in sys_notes]
        xs, x0, x1 = barlines(B, s, note_xs)
        segs = []
        prev = x0
        for x in list(xs) + [x1]:
            segs.append({"xa": round(prev, 1), "xb": round(x, 1)})
            prev = x
        for sg in segs:
            sg["nb"] = [n["bar"] for n in sys_notes
                        if n.get("bar") and sg["xa"] <= n["x"] < sg["xb"]]
            sg["multi"] = is_multirest(B, s, sg["xa"], sg["xb"])
        sys_bars = [n["bar"] for n in sys_notes if n.get("bar")]
        fb = min(sys_bars) if sys_bars else (prev_last or first_bar)
        lb = max(sys_bars) if sys_bars else (prev_last or last_bar)
        labels = assign_bars(segs, fb or 1, lb or 1)
        if sys_bars:
            prev_last = max(sys_bars)
        for sg, lab in zip(segs, labels):
            sg["label"] = lab
            del sg["nb"]
            del sg["multi"]
        out[str(si)] = segs
    json.dump(out, open(f"work/bars_auto_p{p}.json", "w"), indent=0)
    print(p, len(ST), "systems,", sum(len(v) for v in out.values()), "segments")


if __name__ == "__main__":
    for p in map(int, sys.argv[1:]):
        run(p)
