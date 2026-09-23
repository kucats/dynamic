"""Shared helpers for the DYNAMIC score-reading pipeline (staff detection, pitch spelling)."""
from __future__ import annotations
import numpy as np

LET = 'CDEFGAB'
SEMI = [0, 2, 4, 5, 7, 9, 11]
SOL = {'C': 'ド', 'D': 'レ', 'E': 'ミ', 'F': 'ファ', 'G': 'ソ', 'A': 'ラ', 'B': 'シ'}
ACC_IN = {'': 0, 'n': 0, 'b': -1, '#': 1, 'bb': -2, '##': 2}
ACC_OUT = {0: '', -1: '♭', 1: '♯', -2: '𝄫', 2: '𝄪'}


def staves(B):
    """Detect 5-line staves in a boolean (dark=True) 300-dpi page image. Returns list of 5 y-values."""
    H, W = B.shape
    allst = []
    for x0 in (500, 900, 1400, 1900, 2300):
        rows = B[:, x0:x0 + 300].sum(1)
        cand = [y for y in range(H) if rows[y] > 0.6 * 300]
        g: list[list[int]] = []
        for y in cand:
            if g and y - g[-1][-1] <= 2:
                g[-1].append(y)
            else:
                g.append([y])
        ys = [sum(q) / len(q) for q in g]
        i = 0
        while i + 4 < len(ys):
            s = ys[i:i + 5]
            d = np.diff(s)
            if d.max() - d.min() < 7 and 18 < d.mean() < 34:
                allst.append(s)
                i += 5
            else:
                i += 1
    allst.sort(key=lambda s: s[0])
    merged: list[list[list[float]]] = []
    for s in allst:
        if merged and abs(merged[-1][0][0] - s[0]) < 80:
            merged[-1].append(s)
        else:
            merged.append([s])
    return [list(np.mean(np.array(grp), axis=0)) for grp in merged]


def parse_pitch(p: str):
    """'Bb4' -> ('B', -1, 4)"""
    return p[0], ACC_IN[p[1:-1]], int(p[-1])


def midi(L, a, o):
    return 12 * (o + 1) + SEMI[LET.index(L)] + a


def transpose(L, a, o, dl, ds):
    """Move by dl letter steps and ds semitones, keeping correct spelling."""
    base = midi(L, a, o)
    idx = LET.index(L) + dl
    no = o + idx // 7
    nl = LET[idx % 7]
    return nl, base + ds - midi(nl, 0, no), no


def label(L, a, o):
    return [SOL[L] + ACC_OUT[a], o, midi(L, a, o)]

# horn crook -> (letter steps, semitones) from written to sounding pitch
HORN_KEYS = {'F': (-4, -7), 'E': (-5, -8), 'Eb': (-5, -9), 'D': (-6, -10), 'C': (-7, -12), 'G': (-3, -5), 'Bb': (-1, -2)}
