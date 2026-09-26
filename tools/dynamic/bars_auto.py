#!/usr/bin/env python3
"""Generate work/bars_auto_pNN.json: auto-detected barline segments per system,
with labels estimated from the notes' bar numbers in work/final_pNN.json.

Usage: python3 tools/dynamic/bars_auto.py PAGE [PAGE...]
Output: work/bars_auto_pPAGE.json = {"<sys>": [{"xa","xb","label"}, ...]}
Review/overlay with: python3 tools/dynamic/bars_overlay.py PAGE
"""
import cv2, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import staves
from barlines import barlines, is_multirest, assign_bars


def run(p):
    im = cv2.imread(f'work/p{p}.png', 0)
    B = im < 140
    ST = staves(B)
    try:
        d = json.load(open(f'work/final_p{p}.json'))
        notes = d['notes']
    except FileNotFoundError:
        notes = []
    # bar numbers per system
    nb = {}
    for n in notes:
        if n.get('bar') is not None:
            nb.setdefault(n['sys'], []).append((n['x'], n['bar']))
    out = {}
    for si, s in enumerate(ST, 1):
        xs_note = [x for x, _ in nb.get(si, [])]
        m, x0, x1 = barlines(B, s, xs_note)
        bounds = [x0] + m + [x1]
        segs = []
        for a, b in zip(bounds, bounds[1:]):
            inside = [bar for x, bar in nb.get(si, []) if a <= x < b]
            segs.append({'xa': round(float(a), 1), 'xb': round(float(b), 1),
                         'nb': inside, 'multi': bool(is_multirest(B, s, a, b))})
        labels = assign_bars(segs, 1, max([b for _, b in nb.get(si, [])] or [1]))
        out[str(si)] = [{'xa': g['xa'], 'xb': g['xb'], 'label': lab}
                        for g, lab in zip(segs, labels)]
    json.dump(out, open(f'work/bars_auto_p{p}.json', 'w'), indent=0)
    print(p, 'systems', len(out), 'segs', sum(len(v) for v in out.values()))


if __name__ == '__main__':
    for p in map(int, sys.argv[1:]):
        run(p)
