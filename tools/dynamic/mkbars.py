"""Generate work/bars_auto_pPAGE.json: barline segments per system with guessed labels.

Usage: python3 tools/dynamic/mkbars.py PAGE [FIRST_BAR LAST_BAR]
Reads work/pPAGE.png and work/final_pPAGE.json (notes must carry 'bar' already).
FIRST_BAR/LAST_BAR default to the min/max of meta.bars in final_pPAGE.json.
Output segments: {"xa","xb","label"} — labels are guesses for the reader to correct.
"""
import cv2, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import staves
from barlines import barlines, is_multirest, assign_bars


def page_bar_range(meta):
    b = meta.get("bars")
    if isinstance(b, list):
        return int(b[0]), int(b[1])
    if isinstance(b, dict):
        lo = min(v[0] for v in b.values()); hi = max(v[1] for v in b.values())
        return int(lo), int(hi)
    return None, None


def run(p, first=None, last=None):
    im = cv2.imread(f'work/p{p}.png', 0)
    B = im < 140
    ST = staves(B)
    fin = json.load(open(f'work/final_p{p}.json'))
    notes = fin.get('notes', [])
    if first is None or last is None:
        first, last = page_bar_range(fin.get('meta', {}))
    first = first or 1
    out = {}
    for si, s in enumerate(ST, 1):
        nxs = [n['x'] for n in notes if n.get('sys') == si]
        xs, x0, x1 = barlines(B, s, nxs)
        bounds = [x0] + list(xs) + [x1]
        segs = []
        for a, b in zip(bounds, bounds[1:]):
            if b - a < 30:
                continue
            nb = [n['bar'] for n in notes
                  if n.get('sys') == si and a <= n['x'] < b and n.get('bar') is not None]
            segs.append(dict(xa=int(round(a)), xb=int(round(b)), nb=nb,
                             multi=is_multirest(B, s, a, b)))
        labs = assign_bars(segs, first, last or first or 0)
        out[str(si)] = [dict(xa=g['xa'], xb=g['xb'], label=g_lab)
                        for g, g_lab in zip(segs, labs)]
    dst = f'work/bars_auto_p{p}.json'
    json.dump(out, open(dst, 'w'), ensure_ascii=False, indent=1)
    tot = sum(len(v) for v in out.values())
    unl = sum(1 for v in out.values() for g in v if not g['label'])
    print(f'{dst}: {len(out)} systems, {tot} segments, {unl} unlabeled')


if __name__ == '__main__':
    p = int(sys.argv[1])
    run(p, int(sys.argv[2]) if len(sys.argv) > 2 else None,
        int(sys.argv[3]) if len(sys.argv) > 3 else None)
