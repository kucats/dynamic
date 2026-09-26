#!/usr/bin/env python3
"""Generate work/bars_auto_pNN.json for the bar-number pass.

Detects barline segments per system (common.staves numbering), flags likely
multi-bar rests, and guesses labels from the bar numbers already assigned to
notes in work/final_pNN.json. Output feeds work/bars_overlay.py and is then
corrected by hand into work/bars_pNN.json.

Usage: python3 work/mk_bars_auto.py PAGE
"""
import json
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import staves                       # noqa: E402
from barlines import barlines, is_multirest, assign_bars  # noqa: E402

p = int(sys.argv[1])
B = cv2.imread(f'work/p{p}.png', 0) < 140
ST = staves(B)
try:
    cands = json.load(open(f'work/cand_p{p}.json'))['cands']
except FileNotFoundError:
    cands = []
try:
    notes = json.load(open(f'work/final_p{p}.json'))['notes']
except FileNotFoundError:
    notes = []
    print('no final file; labels guessed from scratch')
xs_ref = [c['x'] for c in cands] if cands else [n['x'] for n in notes]
out = {}
for i, s in enumerate(ST):
    sn = i + 1
    xs, x0, x1 = barlines(B, s, xs_ref)
    bnds = [x0] + xs + [x1]
    segs = []
    for a, b in zip(bnds, bnds[1:]):
        if b - a < 30:
            continue
        nb = [n['bar'] for n in notes if n['sys'] == sn and n.get('bar') and a <= n['x'] < b]
        segs.append({'xa': int(a), 'xb': int(b), 'nb': nb, 'multi': is_multirest(B, s, a, b)})
    sb = [n['bar'] for n in notes if n['sys'] == sn and n.get('bar')]
    lab = assign_bars(segs, min(sb) if sb else 1, max(sb) if sb else len(segs))
    out[str(sn)] = [{'xa': sg['xa'], 'xb': sg['xb'], 'label': lab[j]} for j, sg in enumerate(segs)]
json.dump(out, open(f'work/bars_auto_p{p}.json', 'w'), indent=1)
print('systems:', {k: len(v) for k, v in out.items()})
