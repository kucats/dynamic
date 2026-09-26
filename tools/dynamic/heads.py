import sys, cv2, numpy as np
sys.path.insert(0, 'tools/dynamic')
from common import staves

NAMES = 'CDEFGAB'

def pitch_of(y, top, sp):
    k = int(round((y - top) / (sp / 2.0)))
    L, o = 3, 5
    if k > 0:
        for _ in range(k):
            L -= 1
            if L < 0: L, o = 6, o - 1
    elif k < 0:
        for _ in range(-k):
            L += 1
            if L > 6: L, o = 0, o + 1
    return f"{NAMES[L]}{o}"

def detect(page):
    im = cv2.imread(f'work/p{page}.png', 0)
    B = (im < 128).astype(np.uint8)
    ss = staves(B)
    out = {}
    for si, s in enumerate(ss, 1):
        top, bot = float(s[0]), float(s[4])
        step = float(s[1] - s[0])
        y0 = int(top - 4 * step); y1 = int(bot + 4 * step)
        band = B[y0:y1, :].copy()
        # erase staff lines: rows where dark run is long
        for ly in s:
            yy = int(round(ly)) - y0
            for dy in (-2, -1, 0, 1, 2):
                r = yy + dy
                if 0 <= r < band.shape[0]:
                    # only erase where the pixel is part of a long horizontal run
                    row = band[r]
                    band[r] = np.where(_hrun(row) > 14, 0, row)
        # erase beams / long horizontal bars
        rowrun = band.mean(1)
        for r in range(band.shape[0]):
            band[r] = np.where(_hrun(band[r]) > 40, 0, band[r])
        # vertical stems survive; heads ~ ellipse. open with small ellipse to isolate heads
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        op = cv2.morphologyEx(band, cv2.MORPH_OPEN, k)
        n, lab, st, cen = cv2.connectedComponentsWithStats(op)
        heads = []
        for i in range(1, n):
            x, y, w, h, a = st[i]
            if 10 <= w <= 40 and 8 <= h <= 34 and a >= 60:
                cx, cy = cen[i]
                heads.append((round(cx, 1), round(cy + y0, 1), w, h, a))
        out[si] = (top, step, sorted(heads))
    return out

def _hrun(row):
    # length of consecutive dark run ending at each pixel
    out = np.zeros(len(row), dtype=np.int32)
    run = 0
    for i, v in enumerate(row):
        run = run + 1 if v else 0
        out[i] = run
    # now length of run containing each pixel: propagate backwards
    res = np.zeros(len(row), dtype=np.int32)
    run = 0
    for i in range(len(row) - 1, -1, -1):
        run = run + 1 if row[i] else 0
        if row[i]:
            res[i] = max(res[i], run + out[i] - 1)
    return res

if __name__ == '__main__':
    page = sys.argv[1]
    d = detect(page)
    for si, (top, step, heads) in d.items():
        print(f'== sys{si} top={top:.0f} step={step:.1f} heads={len(heads)}')
        for x, y, w, h, a in heads:
            print(f'   x={x:7.1f} y={y:7.1f} w={w:2d} h={h:2d} a={a:4d} -> {pitch_of(y, top, step)}')
