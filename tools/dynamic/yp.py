import sys, cv2, numpy as np
sys.path.insert(0, 'tools/dynamic')
from common import staves

NAMES = ['C', 'D', 'E', 'F', 'G', 'A', 'B']

def pitch_of(y, top, sp):
    k = int(round((y - top) / (sp / 2.0)))
    # k=0 -> F5; each +1 step down one diatonic step
    L, o = 3, 5  # F5
    d = k
    if d > 0:
        for _ in range(d):
            L -= 1
            if L < 0:
                L = 6
                o -= 1  # passed C down to B: octave drops
    elif d < 0:
        for _ in range(-d):
            L += 1
            if L > 6:
                L = 0
                o += 1  # passed B up to C: octave rises
    return f"{NAMES[L]}{o}"

if __name__ == '__main__':
    page = sys.argv[1]
    sysp = int(sys.argv[2])
    im = cv2.imread(f'work/p{page}.png', 0)
    ss = staves(im < 128)
    top = float(ss[sysp - 1][0])
    sp = float(ss[sysp - 1][1] - ss[sysp - 1][0])
    print(f'sys{sysp}: top={top:.1f} halfstep={sp / 2:.2f}px')
    for arg in sys.argv[3:]:
        y = float(arg)
        print(f'  y={y} -> {pitch_of(y, top, sp)}')
