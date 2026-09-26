"""Generate work/bars_auto_pNN.json for a page: detected barline segments + label guesses.
Usage: python3 tools/dynamic/mk_bars_auto.py PAGE   (needs work/pPAGE.png and work/final_pPAGE.json if notes exist)
"""
import cv2, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import staves
from barlines import barlines, is_multirest, assign_bars

p = int(sys.argv[1])
im = cv2.imread(f'work/p{p}.png', 0)
B = im < 140
ST = staves(B)
notes = []
try:
    notes = json.load(open(f'work/final_p{p}.json'))['notes']
except FileNotFoundError:
    print('no final file; labels blank')
nxs = [n['x'] for n in notes]
out = {}
for si, s in enumerate(ST, 1):
    xs, x0, x1 = barlines(B, s, nxs)
    xs = [x0] + xs + [x1]
    segs = []
    for a, b in zip(xs, xs[1:]):
        if b - a < 30:
            continue
        nb = [n['bar'] for n in notes if n['sys'] == si and a - 20 <= n['x'] < b - 10 and n.get('bar')]
        segs.append(dict(xa=round(a, 1), xb=round(b, 1), label='',
                         nb=nb, multi=is_multirest(B, s, a, b)))
    labels = assign_bars(segs, notes[0]['bar'] if notes else 1, notes[-1]['bar'] if notes else len(segs))
    for g, l in zip(segs, labels):
        g['label'] = l
        del g['nb'], g['multi']
    out[str(si)] = segs
json.dump(out, open(f'work/bars_auto_p{p}.json', 'w'), indent=1)
print(f'bars_auto_p{p}.json:', {k: len(v) for k, v in out.items()})
