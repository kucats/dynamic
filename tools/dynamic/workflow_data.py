"""Read-only, conservative adapter for existing DYNAMIC part/page documents.

The filename and part.json, not a legacy notes document's `page` field, define
physical page identity. No OCR, rendering, transcription or auto-approval occurs.
"""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re

STAGES = ("source", "bars", "pitch", "rhythm", "audit")
SEMANTICS_VERSION = "dynamic-workflow/1"
# Only known timing fields are removed. Unknown fields conservatively affect pitch.
TIMING_FIELDS = {"dur", "off", "tie_from_prev", "tie_to_next", "tuplet"}
TIMING_META = {"meters", "tempos", "repeats"}
PRESENTATION = {"title", "subtitle", "pdf"}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or "\\" in relative:
        raise ValueError("path must be relative and contained")
    path = root / rel
    for ancestor in (path, *path.parents):
        if ancestor == root:
            break
        if ancestor.is_symlink():
            raise ValueError(f"symlinks are not supported: {relative}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("path escapes workspace")
    return path


def read_json(path: Path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f"non-finite JSON number: {value}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=constant)


def positive_int(value) -> bool:
    return type(value) is int and value > 0


def finite(value) -> bool:
    return type(value) is int or (type(value) is float and math.isfinite(value))


def bar_range(label) -> tuple[int, int]:
    match = re.fullmatch(r"([1-9][0-9]*)(?:[–—-]([1-9][0-9]*))?", str(label))
    if not match:
        raise ValueError(f"invalid bar label: {label!r}")
    first, last = int(match[1]), int(match[2] or match[1])
    if last < first:
        raise ValueError("descending bar range")
    return first, last


class Inputs:
    """One immutable-in-use snapshot; callers re-read before committing receipts."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.cfg = read_json(safe_path(self.root, "part.json"))
        if not isinstance(self.cfg, dict) or not isinstance(self.cfg.get("id"), str) or not self.cfg["id"]:
            raise ValueError("part.json requires an id")
        source = self.cfg.get("source", {})
        if not isinstance(source, dict) or not re.fullmatch(r"[0-9a-fA-F]{64}", str(source.get("sha256", ""))):
            raise ValueError("part.json requires source.sha256")
        movements = self.cfg.get("movements")
        if not isinstance(movements, list) or not movements:
            raise ValueError("part.json requires movements")
        self.movements = {}
        pages = set()
        for movement in movements:
            if not isinstance(movement, dict) or not isinstance(movement.get("key"), str) or not movement["key"]:
                raise ValueError("movement requires a string key")
            if movement["key"] in self.movements:
                raise ValueError("duplicate movement key")
            selected = movement.get("pages")
            if not isinstance(selected, list) or not selected or not all(map(positive_int, selected)) or selected != sorted(set(selected)):
                raise ValueError("movement pages must be positive, unique and ascending")
            if movement.get("last") is not None and not positive_int(movement["last"]):
                raise ValueError("movement last bar must be positive when supplied")
            self.movements[movement["key"]] = movement
            pages.update(selected)
        self.pages = sorted(pages)
        source_pages = source.get("pages")
        if not isinstance(source_pages, list) or not all(map(positive_int, source_pages)) or source_pages != self.pages:
            raise ValueError("source.pages must match movement physical pages")
        if not positive_int(self.cfg.get("dpi", 300)):
            raise ValueError("dpi must be a positive integer")
        self.splits = {}
        for split in self.cfg.get("splits", []):
            if not isinstance(split, dict) or split.get("page") not in pages or not positive_int(split.get("first_system")):
                raise ValueError("invalid movement split")
            if split["page"] in self.splits or split.get("movement") not in self.movements:
                raise ValueError("duplicate split or unknown movement")
            self.splits[split["page"]] = split
        for page in self.pages:
            here = [key for key, m in self.movements.items() if page in m["pages"]]
            split = self.splits.get(page)
            if len(here) > 2 or (len(here) == 2 and (not split or split["movement"] != here[1])):
                raise ValueError("shared pages require an explicit supported movement split")
            if split and (len(here) != 2 or split["movement"] != here[1]):
                raise ValueError("movement split does not match page membership")
        self.bars, self.notes = {}, {}
        for page in self.pages:
            for name, target in (("bars", self.bars), ("notes", self.notes)):
                path = safe_path(self.root, f"pages/{name}_p{page:02d}.json")
                target[page] = read_json(path) if path.exists() else None
                if target[page] is not None and not isinstance(target[page], dict):
                    raise ValueError(f"{name}_p{page:02d}.json must be an object")
                if name == "notes" and target[page] is not None:
                    if not isinstance(target[page].get("notes"), list) or not all(isinstance(n, dict) for n in target[page]["notes"]):
                        raise ValueError("notes document requires a list of note objects")
                    if not isinstance(target[page].get("meta", {}), dict):
                        raise ValueError("notes meta must be an object")
        self.context = {k: v for k, v in self.cfg.items() if k not in PRESENTATION}
        self.pitch_context = {k: v for k, v in self.context.items() if k not in {"movements", "status", "limitations"}}
        self.pitch_context["movements"] = [
            {k: v for k, v in m.items() if k not in {"meters", "tempos", "sequence", "title", "short"}}
            for m in movements]
        self.source_context = {"id": self.cfg["id"], "source": source, "dpi": self.cfg.get("dpi", 300),
                               "movements": [{"key": m["key"], "pages": m["pages"]} for m in movements],
                               "splits": self.cfg.get("splits", [])}
        self.numbering_context = {"movements": [{"key": m["key"], "last": m.get("last"), "pages": m["pages"]} for m in movements],
                                  "splits": self.cfg.get("splits", [])}

    def movement_for(self, page: int, system: int) -> str:
        here = [key for key, m in self.movements.items() if page in m["pages"]]
        split = self.splits.get(page)
        return split["movement"] if split and system >= split["first_system"] else here[0]

    def output(self, page: int, stage: str) -> dict[str, str]:
        notes = self.notes[page]
        if stage == "source":
            value = {"physical_page": page, **self.source_context}
        elif stage == "bars":
            value = None if self.bars[page] is None else {"bars": self.bars[page], "numbering": self.numbering_context}
        elif stage == "pitch":
            value = None if notes is None else {
                **{k: v for k, v in notes.items() if k not in {"notes", "meta", "rests"}},
                "notes": [{k: v for k, v in n.items() if k not in TIMING_FIELDS} for n in notes["notes"]],
                "meta": {k: v for k, v in notes.get("meta", {}).items() if k not in TIMING_META},
                "context": self.pitch_context}
        else:
            value = None if notes is None else {"notes": notes, "context": self.context}
        return {} if value is None else {"data": digest(value)}

    def segments(self, page: int):
        bars = self.bars[page]
        if not bars:
            raise ValueError(f"p{page}: bar map missing or empty")
        if any(not re.fullmatch(r"[1-9][0-9]*", key) for key in bars):
            raise ValueError(f"p{page}: system keys must be positive canonical integers")
        for sid in sorted(bars, key=int):
            segments = bars[sid]
            if not isinstance(segments, list) or not segments:
                raise ValueError(f"p{page}/s{sid}: empty or invalid segments")
            previous_x = None
            for segment in segments:
                if not isinstance(segment, dict) or not all(finite(segment.get(k)) for k in ("xa", "xb")):
                    raise ValueError(f"p{page}/s{sid}: invalid bar coordinates")
                if segment["xa"] >= segment["xb"] or (previous_x is not None and segment["xa"] < previous_x):
                    raise ValueError(f"p{page}/s{sid}: reversed or overlapping bar geometry")
                previous_x = segment["xb"]
                first, last = bar_range(segment.get("label"))
                yield self.movement_for(page, int(sid)), int(sid), segment, first, last

    def numbering_errors(self, page: int | None = None) -> list[str]:
        previous = {}
        try:
            for physical in self.pages if page is None else [page]:
                for movement, _sid, _segment, first, last in self.segments(physical):
                    if movement not in previous:
                        if page is None and first != 1:
                            raise ValueError(f"{movement}: first bar is {first}, expected 1")
                    elif first != previous[movement] + 1:
                        raise ValueError(f"{movement}/p{physical}: bar {first} follows {previous[movement]}")
                    declared_last = self.movements[movement].get("last")
                    if declared_last is not None and last > declared_last:
                        raise ValueError(f"{movement}: bar exceeds declared last")
                    previous[movement] = last
            if page is None:
                for key, movement in self.movements.items():
                    if movement.get("last") is None or previous.get(key) != movement["last"]:
                        raise ValueError(f"{key}: bar coverage does not reach declared last")
        except (ValueError, TypeError) as exc:
            return [str(exc)]
        return []

    def structural_errors(self, page: int, stage: str) -> list[str]:
        if stage == "source":
            return []
        errors = self.numbering_errors(page)
        if stage == "bars" and any(m.get("last") is None for m in self.movements.values() if page in m["pages"]):
            errors.append("declare the movement last bar before completing numbering")
        if errors or stage == "bars":
            return errors
        notes = self.notes[page]
        if notes is None:
            return [f"p{page}: notes are missing"]
        segments = list(self.segments(page))
        intervals = defaultdict(list)
        for ordinal, note in enumerate(notes["notes"], 1):
            prefix = f"p{page}/note{ordinal}"
            if not positive_int(note.get("sys")) or not positive_int(note.get("bar")) or not all(finite(note.get(k)) for k in ("x", "y")):
                errors.append(f"{prefix}: missing/invalid musical address or coordinates")
                continue
            if not isinstance(note.get("pitch"), str) or not re.fullmatch(r"[A-G](?:#{1,2}|b{1,2}|x)?-?[0-9]+", note["pitch"]):
                errors.append(f"{prefix}: missing/invalid written pitch")
            matches = [(m, first, last) for m, sid, seg, first, last in segments
                       if sid == note["sys"] and first <= note["bar"] <= last and seg["xa"] <= note["x"] <= seg["xb"]]
            if len(matches) != 1:
                errors.append(f"{prefix}: note does not bind to exactly one numbered segment")
                continue
            if stage == "pitch":
                continue
            movement = matches[0][0]
            try:
                # Strings/integers only: floats would hide binary-rounding drift.
                if any(type(note.get(k)) not in (str, int) for k in ("dur", "off")):
                    raise ValueError("timing must use rational strings or integers")
                duration, offset = Fraction(note["dur"]), Fraction(note["off"])
                if duration <= 0 or offset < 0:
                    raise ValueError("duration must be positive and offset nonnegative")
                meters = self.movements[movement].get("meters", [])
                if not isinstance(meters, list) or not meters:
                    raise ValueError("meter is missing")
                active = None
                last_bar = 0
                for change in meters:
                    if not isinstance(change, list) or len(change) != 2 or not positive_int(change[0]) or change[0] <= last_bar:
                        raise ValueError("meter changes must have ascending positive bar numbers")
                    last_bar = change[0]
                    if change[0] <= note["bar"]:
                        active = Fraction(change[1])
                if active is None or active <= 0 or offset + duration > active:
                    raise ValueError("timing exceeds or has no active meter")
                voice = str(note.get("voice", "1"))
                intervals[(movement, note["bar"], voice)].append((offset, offset + duration, ordinal))
            except (ValueError, TypeError, ZeroDivisionError) as exc:
                errors.append(f"{prefix}: {exc}")
        # This adapter supports monophonic voices, not implicit chords. It never
        # silently interprets overlapping events as a valid chord or fills rests.
        for key, events in intervals.items():
            end = Fraction(0)
            for start, stop, ordinal in sorted(events):
                if start < end:
                    errors.append(f"p{page}/note{ordinal}: overlapping events in {key}")
                end = max(end, stop)
        return errors

    def uncertainties(self, page: int) -> list[str]:
        notes = self.notes[page]
        return [] if notes is None else [f"p{page}/note{i}: {n['uncertain']}"
                                        for i, n in enumerate(notes["notes"], 1) if n.get("uncertain")]

    def snapshot_hash(self) -> str:
        return digest({"config": self.cfg, "bars": self.bars, "notes": self.notes})
