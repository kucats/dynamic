"""Draft bar-segment labels for one page -> work/bars_auto_pPAGE.json.

Barlines come from barlines.py driven by the reviewed staff layout
(work/systems_pPAGE.json when present, else auto-detection); labels are seeded
from note bar numbers in work/final_pPAGE.json when it exists. This is a DRAFT —
verify with bars_overlay.py and write bars_pNN.json by hand.
"""
import cv2, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_systems
from barlines import barlines, is_multirest, assign_bars

p = int(sys.argv[1])
im = cv2.imread(f'work/p{p}.png', 0); B = im < 140
ST = load_systems(p, B)
notes = []
try:
    notes = json.load(open(f'work/final_p{p}.json'))['notes']
except FileNotFoundError:
    pass
# assign notes to systems by proximity to each system's midline (n['sys'] is advisory)
def sys_of(y):
    return min(range(len(ST)), key=lambda k: abs(y - (ST[k][0] + ST[k][4]) / 2)) + 1
out = {}
for si, s in enumerate(ST, 1):
    sysnotes = [n for n in notes if sys_of(n['y']) == si]
    xs, x0, x1 = barlines(B, s, [n['x'] for n in sysnotes])
    edges = [x0] + xs + [x1]
    segs = []
    for a, b in zip(edges, edges[1:]):
        nb = [n['bar'] for n in sysnotes if n.get('bar') is not None and a <= n['x'] < b]
        segs.append(dict(xa=int(a), xb=int(b), nb=nb, multi=bool(is_multirest(B, s, a, b))))
    nbars = [n['bar'] for n in sysnotes if n.get('bar') is not None]
    fb, lb = (min(nbars), max(nbars)) if nbars else (None, None)
    labs = assign_bars(segs, fb if fb is not None else 0, lb if lb is not None else 0) if segs else []
    for g, l in zip(segs, labs):
        g['label'] = l
    for g in segs:
        g.pop('nb'); g.pop('multi')
    out[str(si)] = segs
json.dump(out, open(f'work/bars_auto_p{p}.json', 'w'), indent=1)
print(p, 'systems', len(ST), 'segs', sum(len(v) for v in out.values()))
