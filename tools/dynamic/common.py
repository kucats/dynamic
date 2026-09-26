"""Shared helpers for the DYNAMIC score-reading pipeline (staff detection, pitch spelling)."""
from __future__ import annotations

import json
import os


def load_systems(page: int, B):
    """Reviewed staff layout: prefer work/systems_p<page>.json (list of 5 staff-line y's) when present."""
    f = f"work/systems_p{page}.json"
    if os.path.exists(f):
        return json.load(open(f))["systems"]
    return staves(B)

LET = 'CDEFGAB'
SEMI = [0, 2, 4, 5, 7, 9, 11]
SOL = {'C': 'ド', 'D': 'レ', 'E': 'ミ', 'F': 'ファ', 'G': 'ソ', 'A': 'ラ', 'B': 'シ'}
ACC_IN = {'': 0, 'n': 0, 'b': -1, '#': 1, 'bb': -2, '##': 2}
ACC_OUT = {0: '', -1: '♭', 1: '♯', -2: '𝄫', 2: '𝄪'}


def staves(B):
    """Detect 5-line staves in a boolean (dark=True) 300-dpi page image. Returns list of 5 y-values."""
    import numpy as np

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

GERMAN = {'C': 'C', 'D': 'D', 'E': 'E', 'F': 'F', 'G': 'G', 'A': 'A', 'B': 'H'}


def label_german(L, a, o):
    """German-style letter names used by the trombone parts: H = B natural, B♭ written 'B♭'."""
    name = 'B♭' if (L == 'B' and a == -1) else GERMAN[L] + ACC_OUT[a]
    return [name, o, midi(L, a, o)]


# basic B♭ tenor trombone slide positions (first choice), by MIDI number
TROMBONE_POS = {
    40: 7, 41: 6, 42: 5, 43: 4, 44: 3, 45: 2, 46: 1, 47: 7, 48: 6, 49: 5, 50: 4, 51: 3, 52: 2, 53: 1,
    54: 5, 55: 4, 56: 3, 57: 2, 58: 1, 59: 4, 60: 3, 61: 2, 62: 1, 63: 3, 64: 2, 65: 1, 66: 3, 67: 2,
    68: 3, 69: 2, 70: 1, 71: 2, 72: 1, 73: 2, 74: 1, 75: 3, 76: 2, 77: 1, 78: 2, 79: 1,
}
