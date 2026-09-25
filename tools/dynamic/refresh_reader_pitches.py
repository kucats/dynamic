#!/usr/bin/env python3
"""Refresh generated reader pitch labels from reviewed notes_pNN.json files.

This does not need the original score PDF: it preserves the generated system images
and layout, checks note ordering and rhythm against the reviewed source data, and
recomputes pitch-dependent labels and uncertainty flags.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CLARINET_KEYS, HORN_KEYS, TROMBONE_POS, label, label_german, parse_pitch, transpose  # noqa: E402

OUT = ROOT / "public/reader/data"


def refresh(part_dir: Path) -> tuple[str, int, int]:
    cfg = json.loads((part_dir / "part.json").read_text(encoding="utf-8"))
    path = OUT / f"{cfg['id']}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("id") != cfg["id"] or data.get("schema") != 1:
        raise ValueError(f"{path}: generated reader id/schema does not match {part_dir}")

    pages = sorted({p for m in cfg["movements"] for p in m["pages"]})
    source_by_system: dict[tuple[int, int], list[dict]] = {}
    for page in pages:
        page_data = json.loads((part_dir / f"pages/notes_p{page:02d}.json").read_text(encoding="utf-8"))
        for note in page_data["notes"]:
            source_by_system.setdefault((page, int(note["sys"])), []).append(note)

    output_by_system: dict[tuple[int, int], list[dict]] = {}
    for note in data["notes"]:
        index = int(note["s"])
        if index < 0 or index >= len(data["systems"]):
            raise ValueError(f"{path}: note {note.get('id')} refers to missing system {index}")
        system = data["systems"][index]
        if system.get("i") != index:
            raise ValueError(f"{path}: system index mismatch at {index}")
        key = (int(system["page"]), int(system["sys"]))
        output_by_system.setdefault(key, []).append(note)

    if source_by_system.keys() != output_by_system.keys():
        missing = sorted(source_by_system.keys() - output_by_system.keys())
        extra = sorted(output_by_system.keys() - source_by_system.keys())
        raise ValueError(f"{path}: source/reader systems differ (missing={missing}, extra={extra})")

    instrument = cfg.get("instrument", "horn")
    updated = 0
    total = 0
    for key in sorted(source_by_system):
        source_notes = source_by_system[key]
        reader_notes = output_by_system[key]
        if len(source_notes) != len(reader_notes):
            raise ValueError(f"{path}: {key} has {len(source_notes)} source notes but {len(reader_notes)} reader notes")
        for source, reader in zip(source_notes, reader_notes):
            total += 1
            old = source.get("notation") == "old-bass-clef"
            expected = {
                "bar": int(source["bar"]),
                "off": float(Fraction(source["off"])),
                "dur": float(Fraction(source["dur"])),
                "tie": bool(source.get("tie_from_prev")),
                "old": old,
            }
            for field in ("bar", "tie", "old"):
                if reader.get(field) != expected[field]:
                    raise ValueError(f"{path}: {key} note {reader.get('id')} {field} differs from reviewed source")
            for field in ("off", "dur"):
                if not math.isclose(float(reader[field]), expected[field], rel_tol=0, abs_tol=1e-9):
                    raise ValueError(f"{path}: {key} note {reader.get('id')} {field} differs from reviewed source")

            letter, accidental, octave = parse_pitch(source["pitch"])
            written_octave = octave + 1 if old else octave
            if instrument == "trombone":
                written = label_german(letter, accidental, written_octave)
                fields = {"key": "C", "w": written, "f": written, "snd": written,
                          "pos": TROMBONE_POS.get(written[2])}
            elif instrument == "clarinet":
                key_name = source.get("cl_key") or cfg.get("default_cl_key", "A")
                if key_name not in CLARINET_KEYS:
                    raise ValueError(f"{part_dir}: unsupported clarinet key {key_name!r}")
                letter_steps, semitones = CLARINET_KEYS[key_name]
                sounding = transpose(letter, accidental, written_octave, letter_steps, semitones)
                f_side = transpose(*sounding, 1, 2)
                fields = {"key": key_name, "w": label(letter, accidental, written_octave),
                          "f": label(*f_side), "snd": label(*sounding)}
            else:
                key_name = source.get("horn_key") or cfg.get("default_horn_key", "F")
                if key_name not in HORN_KEYS:
                    raise ValueError(f"{part_dir}: unsupported horn key {key_name!r}")
                letter_steps, semitones = HORN_KEYS[key_name]
                sounding = transpose(letter, accidental, written_octave, letter_steps, semitones)
                f_side = transpose(*sounding, 4, 7)
                fields = {"key": key_name, "w": label(letter, accidental, written_octave),
                          "f": label(*f_side), "snd": label(*sounding)}

            fields.update({"p": source["pitch"], "unc": source.get("uncertain") or "", "old": old})
            if any(reader.get(name) != value for name, value in fields.items()):
                updated += 1
                reader.update(fields)

    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return cfg["id"], total, updated


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("parts", nargs="*", type=Path, help="part dynamic directory (default: all project parts)")
    args = ap.parse_args()
    parts = args.parts or sorted(p.parent for p in ROOT.glob("project/**/dynamic/part.json"))
    for part_dir in parts:
        part_id, total, changed = refresh(part_dir)
        print(f"refreshed {part_id}: {changed} pitch records of {total} notes checked")


if __name__ == "__main__":
    main()
