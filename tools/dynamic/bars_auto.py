import cv2, json, sys, os

sys.path.insert(0, os.path.dirname(__file__))
from common import staves
from barlines import barlines, is_multirest

p = int(sys.argv[1])
B = cv2.imread(f'work/p{p}.png', 0) < 140
note_xs = []
cj = f'work/cand_p{p}.json'
if os.path.exists(cj):
    note_xs = [c['x'] for c in json.load(open(cj))['cands']]
out = {}
for i, s in enumerate(staves(B), 1):
    xs, x0, x1 = barlines(B, s, note_xs)
    edges = [x0] + xs + [x1]
    segs = []
    for a, b in zip(edges, edges[1:]):
        if b - a < 12:
            continue
        segs.append({'xa': round(a), 'xb': round(b),
                     'multi': bool(is_multirest(B, s, a, b)), 'label': ''})
    out[str(i)] = segs
json.dump(out, open(f'work/bars_auto_p{p}.json', 'w'), indent=0)
print('systems', len(out), 'segs', sum(len(v) for v in out.values()))
