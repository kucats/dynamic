"""Build work/staves_p{page}.json overrides in cand.staves_of format.

Usage: mkstaves.py PAGE y1 y2 ...   (y_i = approx top-line y of each system)
For each top guess, detect the 5 staff lines in three x windows
(500-800, 1400-1700, 2300-2600) and emit {xl,xr,l,r,m} dicts.
"""
import cv2, json, sys
import numpy as np

def five_lines(B, ytop, x0, x1, search=70):
    rows = B[max(0, ytop - search):ytop + search + 140, x0:x1].sum(1)
    n = x1 - x0
    cand = [ytop - search + i for i, v in enumerate(rows) if v > 0.62 * n]
    g = []
    for y in cand:
        if g and y - g[-1][-1] <= 2:
            g[-1].append(y)
        else:
            g.append([y])
    ys = [sum(q) / len(q) for q in g]
    # choose 5 consecutive lines with spacing 18-34 px near ytop
    best = None
    for i in range(len(ys) - 4):
        s = ys[i:i + 5]
        d = np.diff(s)
        if d.max() - d.min() < 7 and 18 < d.mean() < 34:
            if best is None or abs(s[0] - ytop) < abs(best[0] - ytop):
                best = s
    return best

def main():
    p = int(sys.argv[1]); tops = [int(v) for v in sys.argv[2:]]
    B = cv2.imread(f'work/p{p}.png', 0) < 140
    out = []
    for t in tops:
        m = five_lines(B, t, 1400, 1700)
        l = five_lines(B, t, 500, 800)
        r = five_lines(B, t, 2300, 2600)
        if m is None:
            m = l or r
        assert m is not None, f'no staff near y={t}'
        l = l or m
        r = r or m
        out.append(dict(xl=650, xr=2450, l=l, r=r, m=m))
    json.dump(out, open(f'work/staves_p{p}.json', 'w'), indent=0)
    print(p, 'systems:', len(out))
    for i, s in enumerate(out, 1):
        print(' ', i, 'top-m', round(s['m'][0]), 'sp', round((s['m'][4]-s['m'][0])/4, 1),
              'tilt', round(s['r'][0]-s['l'][0], 1))

if __name__ == '__main__':
    main()
