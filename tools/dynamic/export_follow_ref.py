#!/usr/bin/env python3
"""Export score-following reference streams from decoded part JSONs.

Emits, per work and per movement:
  - tutti event stream: all parts' note onsets on a beat grid (sounding pitch)
  - per-part event stream: that part's onsets only

Format (JSON):
  {"schema":1, "work":..., "movement":..., "beats_per_bar_default":...,
   "events":[[beat_from_movement_start, midi, part_id], ...],
   "bar_starts":[[bar, beat], ...],
   "meter":[[bar,"4/4"],...], "tempo":[[bar,bpm],...]}

beat values are movement-local quarter-note beats; midi is SOUNDING pitch
(transpositions applied). Uncertain (`unc`) and `sim` flags are kept: consumers
may drop them.

Run: python3 tools/dynamic/export_follow_ref.py <composer>/<work> [out_dir]
"""
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "dynamic"))
from common import CLARINET_KEYS, HORN_KEYS, TRUMPET_KEYS, midi, parse_pitch  # noqa

DUR_RE = re.compile(r"^(\d+)(?:/(\d+))?(\.)?$")


def dur_beats(d):
    if d is None:
        return 1.0
    s = str(d).strip()
    named = {"w": 4.0, "h": 2.0, "q": 1.0, "8": 0.5, "t8": 1/3, "16": 0.25,
             "t16": 1/6, "32": 0.125, "4": 1.0, "2": 2.0, "1": 4.0}
    if s in named:
        return named[s]
    m = DUR_RE.match(s)
    if m:
        v = int(m.group(1)) / int(m.group(2) or 1) * 4.0
        if m.group(3):
            v *= 1.5
        return v
    try:
        f = float(s)
        return f * 4 if f <= 1 else f
    except ValueError:
        return 1.0


def off_beats(o):
    if o in (None, ""):
        return 0.0
    try:
        # source `off` is a fraction of a WHOLE note; convert to beats
        return float(Fraction(str(o))) * 4
    except (ValueError, ZeroDivisionError):
        return 0.0


def sounding_shift(inst, note, default_key):
    if inst == "horn":
        return HORN_KEYS.get(note.get("horn_key") or default_key or "F", (-4, -7))[1]
    if inst == "clarinet":
        return CLARINET_KEYS.get(note.get("cl_key") or default_key or "A", (-2, -3))[1]
    if inst == "trumpet":
        return TRUMPET_KEYS.get(note.get("horn_key") or default_key or "C", (0, 0))[1]
    if inst == "english-horn":
        return -7
    if inst in ("contrabass", "bass"):
        return -12
    return 0


def meter_bpb(meter):
    try:
        num, den = meter.split("/")
        return float(Fraction(num) / Fraction(den) * 4)
    except Exception:
        return 4.0


def collect(work_rel):
    """-> {mvt: {"events": [(beat, midi, part)], "meters":..., "tempos":...}}"""
    work_dir = ROOT / "project" / work_rel
    mvts_data = {}
    for part_dir in sorted(work_dir.iterdir()):
        dyn = part_dir / "dynamic"
        pj = dyn / "part.json"
        if not pj.exists():
            continue
        meta = json.loads(pj.read_text())
        inst = meta.get("instrument")
        part_id = meta.get("id") or part_dir.name
        default_key = meta.get("default_horn_key") or meta.get("default_cl_key")
        mvts = {m["key"]: m for m in meta.get("movements", [])}
        if not mvts:
            continue
        page2mvt = {}
        for k, m in mvts.items():
            mvts_data.setdefault(k, {"events": [], "meters": m.get("meters"), "tempos": m.get("tempos")})
            for p in m.get("pages", []):
                page2mvt.setdefault(p, []).append(k)
        for nf in sorted(dyn.glob("pages/notes_p*.json")):
            d = json.loads(nf.read_text())
            # filename page number is authoritative (d["page"] is the source
            # PDF page and does not match part.json's logical pages)
            try:
                page_num = int(nf.stem.rsplit("_p", 1)[1])
            except (IndexError, ValueError):
                page_num = d.get("page")
            cand = page2mvt.get(page_num, list(mvts))
            mb = d.get("meta", {}).get("bars")
            segs = []
            if isinstance(mb, dict):
                segs = [(k, v[0], v[1]) for k, v in mb.items()
                        if isinstance(v, list) and len(v) == 2]
            elif isinstance(mb, list) and len(mb) == 2 and all(isinstance(x, int) for x in mb):
                segs = [(cand[0], mb[0], mb[1])]
            if not segs:
                segs = [(cand[0], None, None)]
            for n in d.get("notes", []):
                if not isinstance(n.get("pitch"), str):
                    continue
                b = n.get("bar") or n.get("page_local_bar")
                if b is None:
                    continue
                mvtk = None
                for k, lo, hi in segs:
                    if lo is None or (lo <= b <= hi):
                        mvtk = k
                        break
                if mvtk is None:
                    mvtk = segs[0][0]
                L, a, o = parse_pitch(n["pitch"])
                mval = midi(L, a, o) + sounding_shift(inst, n, default_key)
                mvts_data[mvtk]["events"].append(
                    (float(b) * 0 + float(b), float(mval), part_id,
                     off_beats(n.get("off")), dur_beats(n.get("dur")),
                     bool(n.get("unc")), bool(n.get("sim"))))
    return mvts_data


def emit(work_rel, out_dir):
    data = collect(work_rel)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for mvtk, md in data.items():
        meters = md["meters"] or [[1, "4/4"]]
        def bpb(bar):
            v = 4.0
            for b, met in meters:
                if b <= bar:
                    v = meter_bpb(met)
                else:
                    break
            return v
        # bar -> beat offset from movement start
        bars = sorted({int(ev[0]) for ev in md["events"]})
        bar_start = {}
        pos = 0.0
        for b in range(min(bars), max(bars) + 1):
            bar_start[b] = pos
            pos += bpb(b)
        # per-part + tutti events with absolute movement beats
        ev_abs = []
        for (barf, mval, pid, off, dur, unc, sim) in md["events"]:
            bar = int(barf)
            if bar not in bar_start:
                continue
            ev_abs.append([round(bar_start[bar] + off, 4), int(mval), pid,
                           bool(unc), bool(sim)])
        ev_abs.sort(key=lambda e: (e[0], e[1]))
        obj = {"schema": 1, "work": work_rel, "movement": mvtk,
               "units": "beats = quarter notes from movement start; midi = sounding pitch",
               "meters": meters, "tempos": md["tempos"],
               "bar_starts": [[b, round(bar_start[b], 4)] for b in sorted(bar_start)],
               "events": ev_abs}
        # tutti file + per-part files
        base = out_dir / f"{mvtk}"
        (base.with_suffix(".tutti.json")).write_text(json.dumps(obj, ensure_ascii=False))
        by_part = {}
        for e in ev_abs:
            by_part.setdefault(e[2], []).append(e)
        for pid, evs in by_part.items():
            pobj = dict(obj); pobj["part"] = pid; pobj["events"] = evs
            (out_dir / f"{mvtk}.{pid}.json").write_text(json.dumps(pobj, ensure_ascii=False))
        print(mvtk, len(ev_abs), "events,", len(by_part), "parts")


if __name__ == "__main__":
    emit(sys.argv[1], sys.argv[2] if len(sys.argv) > 2
         else ROOT / "project" / sys.argv[1] / "follow-ref")
