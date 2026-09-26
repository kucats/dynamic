#!/usr/bin/env python3
"""Extract systems, barlines, and note-head candidates from a rendered page.

Usage: extract_page.py PAGE -- writes work/cells_pN.json with:
  {page, systems: [{sys, top, bot, barlines: [...], heads: [{x,k,w,h,a}]}]}
"""
import sys, json
import cv2
import numpy as np


def detect_systems(B):
    H, W = B.shape
    dens = B[:, 300:2700].mean(axis=1)
    rows = [y for y in range(H) if dens[y] > 0.45]
    groups, prev = [], -9
    for y in rows:
        if y - prev > 18:
            groups.append([])
        groups[-1].append(y)
        prev = y
    # merge line-groups into staves: consecutive groups <60px apart = one staff
    staves = []
    cur = [groups[0]] if groups else []
    for g in groups[1:]:
        if g[0] - cur[-1][-1] < 60:
            cur.append(g)
        else:
            if cur[-1][-1] - cur[0][0] > 60:   # staff spans >= 4 lines ~100px
                staves.append((cur[0][0], cur[-1][-1]))
            cur = [g]
    if cur and cur[-1][-1] - cur[0][0] > 60:
        staves.append((cur[0][0], cur[-1][-1]))
    return staves


def barline_candidates(B, top, bot):
    out = []
    for x in range(300, min(2720, B.shape[1])):
        col = B[top - 8:bot + 12, x]
        inds = np.where(col)[0]
        if len(inds) > 10:
            ex = inds[-1] - inds[0]
            if col.mean() > 0.75 and ex > (bot - top):
                out.append(x)
    groups, prev = [], -9
    for x in out:
        if x - prev > 5:
            groups.append([])
        groups[-1].append(x)
        prev = x
    return [g[len(g) // 2] for g in groups]


def head_candidates(B, top, bot):
    # remove staff lines, then blob
    sub = B[top - 50:bot + 45, :].astype("uint8")
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (55, 1))
    lines = cv2.morphologyEx(sub, cv2.MORPH_OPEN, kernel)
    clean = cv2.subtract(sub, lines)
    n, lab, stats, cent = cv2.connectedComponentsWithStats(clean, 8)
    heads = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if a > 170 and 14 < w < 50 and 10 < h < 50:
            cy = top - 50 + y + h / 2
            k = (bot - cy) / 12.75
            heads.append({"x": int(x + w / 2), "k": round(float(k), 2),
                          "w": int(w), "h": int(h), "a": int(a)})
    heads.sort(key=lambda h: h["x"])
    return heads


def main():
    page = int(sys.argv[1])
    im = cv2.imread(f"work/p{page:02d}.png", 0)
    B = im < 140
    staves = detect_systems(B)
    systems = []
    for si, (top, bot) in enumerate(staves, 1):
        systems.append({
            "sys": si, "top": int(top), "bot": int(bot),
            "barlines": barline_candidates(B, top, bot),
            "heads": head_candidates(B, top, bot),
        })
    json.dump({"page": page, "systems": systems},
              open(f"work/cells_p{page:02d}.json", "w"), indent=1)
    print(f"p{page:02d}: {len(systems)} systems")
    for s in systems:
        print(f"  sys{s['sys']} y[{s['top']},{s['bot']}] bars={s['barlines']} heads={len(s['heads'])}")


if __name__ == "__main__":
    main()
