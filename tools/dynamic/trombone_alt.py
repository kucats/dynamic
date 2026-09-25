#!/usr/bin/env python3
"""Suggest trombone alternate positions that balance slide travel against lip (partial) changes.

Reads the generated reader data (public/reader/data/<id>.json) and the curated option table
(tools/dynamic/trombone_positions.json), finds the cheapest option per note for a whole movement
with a Viterbi search, and writes review suggestions next to the part:

  project/<composer>/<work>/<part>/dynamic/alt-positions.json   machine-readable suggestions
  project/<composer>/<work>/<part>/dynamic/alt-positions.md     Japanese review sheet

Suggestions never change the reader's `pos`. They are an aid for a player or teacher to try,
not a verified reading.

  python3 tools/dynamic/trombone_alt.py                 # all trombone parts, balanced weights
  python3 tools/dynamic/trombone_alt.py --preset lip    # prefer fewer partial changes
  python3 tools/dynamic/trombone_alt.py --check         # fail if committed outputs are stale
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TABLE = Path(__file__).with_name("trombone_positions.json")
BASE_LENGTH_M = 2.74                     # ideal B♭ tenor length; same model as the 3D player
PRESETS = {"slide": 0.4, "balanced": 1.0, "lip": 2.5}   # lip-change weight; slide weight stays 1
REST_GAP_S = 0.3                         # a gap this long gives the slide time to move freely
TIE_PENALTY = 1e6
MIN_GAIN = 0.8                           # a passage must save at least this much cost to be suggested


def extension(pos: int) -> float:
    """Slide extension in metres from first position (half the added tube length)."""
    return BASE_LENGTH_M / 2 * (2 ** ((pos - 1) / 12) - 1)


def load_table(path: Path = TABLE) -> dict[int, list[dict]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {row["midi"]: row["options"] for row in doc["pitches"]}


# ---------- costs ----------
def urgency(ioi: float, gap: float) -> float:
    """How hard a change is for the time available: after a rest or in slow notes both slide
    moves and partial changes are easy; in fast notes both get expensive."""
    return 0.15 if gap >= REST_GAP_S else min(5.0, max(0.35, 0.35 / max(ioi, 0.05)))


def slide_cost(a: dict, b: dict) -> float:
    """Slide travel in decimetres."""
    return 10.0 * abs(extension(b["pos"]) - extension(a["pos"]))


def lip_cost(a: dict, b: dict) -> float:
    """Partial changes; bigger jumps and the higher register cost more."""
    dk = abs(b["partial"] - a["partial"])
    if not dk:
        return 0.0
    return dk ** 1.3 * (1 + 0.08 * max(0, max(a["partial"], b["partial"]) - 6))


def movement_events(data: dict, mvt: dict) -> list[dict]:
    """Notes of one movement in playing order with onset/duration in seconds (first pass, no D.S.)."""
    starts, t, seen = {}, 0.0, set()
    for bar, length, spw, ds in mvt["timeline"]:
        if ds or bar in seen:
            continue
        seen.add(bar)
        starts[bar] = (t, spw)
        t += length * spw
    events = []
    for n in data["notes"]:
        if n["mvt"] != mvt["key"] or n["bar"] not in starts:
            continue
        t0, spw = starts[n["bar"]]
        events.append({"note": n, "t": t0 + n["off"] * spw, "d": n["dur"] * spw})
    events.sort(key=lambda e: (e["t"], e["note"]["id"]))
    return events


def solve(events: list[dict], table: dict[int, list[dict]], lip_weight: float = 1.0) -> list[dict | None]:
    """Cheapest option per event (None for unresolved notes, which also break the chain)."""
    choice: list[dict | None] = [None] * len(events)
    start = 0
    while start < len(events):
        if events[start]["note"]["unc"]:
            start += 1
            continue
        end = start
        while end + 1 < len(events) and not events[end + 1]["note"]["unc"]:
            end += 1
        seg = range(start, end + 1)
        opts = [table[events[i]["note"]["snd"][2]] for i in seg]
        cost = [[o["cost"] for o in opts[0]]]
        back: list[list[int]] = [[-1] * len(opts[0])]
        for j in range(1, len(opts)):
            a, b = events[start + j - 1], events[start + j]
            row, brow = [], []
            for ob in opts[j]:
                best, arg = float("inf"), 0
                for ia, oa in enumerate(opts[j - 1]):
                    c = transition_cost(a, b, oa, ob, lip_weight) + cost[-1][ia]
                    if c < best:
                        best, arg = c, ia
                row.append(best + ob["cost"])
                brow.append(arg)
            cost.append(row)
            back.append(brow)
        k = min(range(len(cost[-1])), key=cost[-1].__getitem__)
        for j in range(len(opts) - 1, -1, -1):
            choice[start + j] = opts[j][k]
            k = back[j][k]
        start = end + 1
    return choice


def standard(table: dict[int, list[dict]], midi: int) -> dict:
    return next(o for o in table[midi] if o.get("standard"))


def totals(path: list[dict | None]) -> tuple[float, int]:
    slide, lips = 0.0, 0
    for a, b in zip(path, path[1:]):
        if a and b:
            slide += abs(extension(b["pos"]) - extension(a["pos"]))
            lips += a["partial"] != b["partial"]
    return slide, lips


def transition_cost(a: dict, b: dict, oa: dict, ob: dict, lip_weight: float) -> float:
    ioi, gap = b["t"] - a["t"], b["t"] - (a["t"] + a["d"])
    if b["note"]["tie"] and b["note"]["snd"][2] == a["note"]["snd"][2]:
        return 0.0 if oa is ob else TIE_PENALTY
    return urgency(ioi, gap) * (slide_cost(oa, ob) + lip_weight * lip_cost(oa, ob))


def path_cost(events, path, lo: int, hi: int, lip_weight: float) -> float:
    c = sum(path[k]["cost"] for k in range(lo, hi + 1) if path[k])
    for k in range(lo, hi):
        if path[k] and path[k + 1]:
            c += transition_cost(events[k], events[k + 1], path[k], path[k + 1], lip_weight)
    return c


def passages(events, chosen, std, lip_weight: float) -> list[dict]:
    """Group consecutive changed notes. Passages are bounded by standard notes, so each can be
    kept or dropped on its own; ones saving less than MIN_GAIN are reverted in `chosen`."""
    out, i = [], 0
    while i < len(events):
        if not chosen[i] or chosen[i] is std[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(events) and chosen[j + 1] and chosen[j + 1] is not std[j + 1]:
            j += 1
        lo, hi = max(0, i - 1), min(len(events) - 1, j + 1)
        gain = path_cost(events, std, lo, hi, lip_weight) - path_cost(events, chosen, lo, hi, lip_weight)
        if gain < MIN_GAIN:
            chosen[i:j + 1] = std[i:j + 1]
            i = j + 1
            continue
        s_std, l_std = totals(std[lo:hi + 1])
        s_alt, l_alt = totals(chosen[lo:hi + 1])
        notes = []
        for k in range(i, j + 1):
            n, c = events[k]["note"], chosen[k]
            notes.append({"id": n["id"], "bar": n["bar"], "pitch": f"{n['snd'][0]}{n['snd'][1]}",
                          "standard": std[k]["pos"], "suggested": c["pos"], "partial": c["partial"],
                          "tuning": c.get("tuning", "")})
        side = lambda k: (f"{events[k]['note']['snd'][0]}{events[k]['note']['snd'][1]}({chosen[k]['pos']})"
                          if 0 <= k < len(events) and chosen[k] else None)
        out.append({"mvt": events[i]["note"]["mvt"], "bars": [events[i]["note"]["bar"], events[j]["note"]["bar"]],
                    "before": side(i - 1), "after": side(j + 1),
                    "notes": notes, "slide_change_m": round(s_alt - s_std, 3), "lip_change": l_alt - l_std,
                    "gain": round(gain, 2)})
        i = j + 1
    return out


def suggest(data: dict, table: dict[int, list[dict]], preset: str) -> dict:
    lip_weight = PRESETS[preset]
    result = {"schema": 1, "part": data["id"], "preset": preset, "lip_weight": lip_weight,
              "model": f"ideal B♭ tenor {BASE_LENGTH_M} m; options from tools/dynamic/trombone_positions.json",
              "movements": []}
    for mvt in data["movements"]:
        events = movement_events(data, mvt)
        if not events:
            continue
        std = [None if e["note"]["unc"] else standard(table, e["note"]["snd"][2]) for e in events]
        chosen = solve(events, table, lip_weight)
        found = passages(events, chosen, std, lip_weight)     # also reverts low-gain passages
        s0, l0 = totals(std)
        s1, l1 = totals(chosen)
        result["movements"].append({
            "key": mvt["key"], "notes": len(events),
            "standard": {"slide_m": round(s0, 2), "lip_changes": l0},
            "suggested": {"slide_m": round(s1, 2), "lip_changes": l1},
            "passages": found})
    return result


def report_md(data: dict, res: dict) -> str:
    label = {"slide": "スライド優先", "balanced": "バランス", "lip": "リップ優先"}[res["preset"]]
    lines = [f"# 替えポジションの提案 — {data['title']}", "",
             f"生成：`python3 tools/dynamic/trombone_alt.py --preset {res['preset']}`（{label}）。"
             "閲覧データの `pos` は変更していません。音程・音色・吹きやすさは奏者が確認してください。",
             "前後の音の（）はポジション。スライド・倍音の変化は、前後の音を含めた区間での基本ポジションとの差です。", ""]
    for m in res["movements"]:
        st, sg = m["standard"], m["suggested"]
        lines += [f"## {m['key']}（{m['notes']}音）", "",
                  f"- 基本ポジション：スライド移動 {st['slide_m']} m、倍音の変化 {st['lip_changes']} 回",
                  f"- 提案どおり：スライド移動 {sg['slide_m']} m、倍音の変化 {sg['lip_changes']} 回", ""]
        if not m["passages"]:
            lines += ["提案なし。", ""]
            continue
        lines += ["| 小節 | 前の音 | 音：基本 → 替え | 次の音 | スライド | 倍音の変化 | 音程 |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]
        for p in m["passages"]:
            bars = str(p["bars"][0]) if p["bars"][0] == p["bars"][1] else f"{p['bars'][0]}–{p['bars'][1]}"
            notes = "、".join(f"{n['pitch']} {n['standard']}→{n['suggested']}" for n in p["notes"])
            tuning = "、".join(sorted({n["tuning"] for n in p["notes"] if n["tuning"]})) or "–"
            lines.append(f"| {bars} | {p['before'] or '–'} | {notes} | {p['after'] or '–'} | "
                         f"{p['slide_change_m'] * 100:+.0f} cm | {p['lip_change']:+d} 回 | {tuning} |")
        lines.append("")
    return "\n".join(lines)


def part_dirs() -> dict[str, Path]:
    out = {}
    for p in ROOT.glob("project/**/dynamic/part.json"):
        cfg = json.loads(p.read_text(encoding="utf-8"))
        if cfg.get("instrument") == "trombone":
            out[cfg["id"]] = p.parent
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--part", action="append", help="reader part id (default: every trombone part)")
    ap.add_argument("--preset", choices=sorted(PRESETS), default="balanced")
    ap.add_argument("--check", action="store_true", help="compare with the committed outputs instead of writing")
    args = ap.parse_args(argv)
    table, dirs, stale = load_table(), part_dirs(), []
    for pid in args.part or sorted(dirs):
        data = json.loads((ROOT / "public/reader/data" / f"{pid}.json").read_text(encoding="utf-8"))
        res = suggest(data, table, args.preset)
        outputs = {dirs[pid] / "alt-positions.json": json.dumps(res, ensure_ascii=False, indent=1) + "\n",
                   dirs[pid] / "alt-positions.md": report_md(data, res)}
        for path, text in outputs.items():
            if args.check:
                if not path.exists() or path.read_text(encoding="utf-8") != text:
                    stale.append(path.relative_to(ROOT))
            else:
                path.write_text(text, encoding="utf-8")
        n = sum(len(m["passages"]) for m in res["movements"])
        print(f"{pid}: {n} passages" + ("" if args.check else f" → {dirs[pid].relative_to(ROOT)}/alt-positions.*"))
    if stale:
        print("stale (rerun tools/dynamic/trombone_alt.py):", *stale, sep="\n  ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
