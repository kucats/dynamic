"""Music and Audiveris geometry, independent of rendering and optional packages.

OMR is a candidate generator. Corrections and rhythm are explicit review inputs;
neither an OMR confidence score nor a successful build constitutes source review.
"""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

CLEFS = {"ALTO": 28, "TENOR": 26, "TREBLE": 34, "BASS": 22, "BARITONE": 24}
POSITIONS = dict(zip(range(40, 71), [
    7, 6, 5, 4, 3, 2, 1, 7, 6, 5, 4, 3, 2, 1, 5, 4, 3, 2, 1,
    4, 3, 2, 1, 3, 2, 1, 3, 2, 3, 2, 1,
]))
ACCIDENTALS = {"SHARP": 1, "FLAT": -1, "NATURAL": 0,
               "DOUBLE_SHARP": 2, "DOUBLE_FLAT": -2}
TPQ = 480


def pitch_info(pitch: str) -> tuple[int, int, str]:
    match = re.fullmatch(r"([A-G])(bb|##|b|#)?(-?\d+)", pitch)
    if not match:
        raise ValueError(f"Invalid scientific pitch {pitch!r}; use B3 internally, H3 for display")
    step, accidental, octave_text = match.groups()
    octave = int(octave_text)
    accidental = accidental or ""
    midi = 12 * (octave + 1) + dict(C=0, D=2, E=4, F=5, G=7, A=9, B=11)[step]
    midi += accidental.count("#") - accidental.count("b")
    if not 0 <= midi <= 127:
        raise ValueError(f"Pitch outside MIDI range: {pitch}")
    display = ("H" if step == "B" and not accidental.startswith("b") else step)
    return midi, octave * 7 + "CDEFGAB".index(step), display + accidental + octave_text


def interpolate(points: list, x: float) -> float:
    if not points:
        raise ValueError("Missing staff line points")
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            if x1 <= x0:
                raise ValueError("Staff line coordinates must increase")
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def staff_geometry(lines: list, x: float) -> tuple[float, float]:
    middle = interpolate(lines[2], x)
    half_step = (interpolate(lines[4], x) - interpolate(lines[0], x)) / 8
    if half_step <= 0:
        raise ValueError("Invalid staff line spacing")
    return middle, half_step


def pitch_at_staff_position(staff_pitch: float, clef: str, fifths: int,
                            accidental: dict | None, state: dict) -> str:
    """Re-derive one written pitch after a reviewed system clef/key override."""
    if clef not in CLEFS or type(fifths) is not int or not -7 <= fifths <= 7:
        raise ValueError("Unsupported corrected clef or key signature")
    diatonic = CLEFS[clef] - round(float(staff_pitch))
    step, octave = "CDEFGAB"[diatonic % 7], diatonic // 7
    if accidental:
        shape = accidental.get("shape")
        if shape not in ACCIDENTALS:
            raise ValueError(f"Unsupported accidental: {accidental}")
        alter = ACCIDENTALS[shape]
        state[(step, octave)] = alter
    else:
        key_alter = (1 if step in "FCGDAEB"[:max(0, fifths)] else
                     -1 if step in "BEADGCF"[:max(0, -fifths)] else 0)
        alter = state.get((step, octave), key_alter)
    return step + {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}[alter] + str(octave)


def read_omr(path: Path, *, default_clef: str, default_fifths: int) -> list[dict]:
    """Read one saved Audiveris sheet; reject multi-staff parts instead of guessing."""
    if default_clef not in CLEFS or not -7 <= default_fifths <= 7:
        raise ValueError("Unsupported clef or key signature")
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if re.fullmatch(r"sheet#\d+/sheet#\d+\.xml", n)]
        if len(names) != 1:
            raise ValueError("Import one page per .omr file (exactly one sheet required)")
        if archive.getinfo(names[0]).file_size > 64 * 1024 * 1024:
            raise ValueError("OMR XML exceeds 64 MiB")
        xml = archive.read(names[0])
        if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
            raise ValueError("XML entities are not supported")
        root = ET.fromstring(xml)

    def bounds(element):
        box = element.find("bounds")
        if box is None:
            raise ValueError(f"Missing bounds for {element.tag}")
        result = [float(box.get(k)) for k in ("x", "y", "w", "h")]
        if not all(math.isfinite(v) for v in result) or min(result[2:]) <= 0:
            raise ValueError("Invalid OMR bounds")
        return result

    def xof(element):
        x, _, width, _ = bounds(element)
        return x + width / 2

    systems = []
    clef, fifths = default_clef, default_fifths
    for system in root.findall(".//system"):
        staves = system.findall("./part/staff")
        if len(staves) != 1:
            raise ValueError("fuyomi v1 requires one played staff per system; split combined parts first")
        lines = [[(float(p.get("x")), float(p.get("y"))) for p in line.findall("point")]
                 for line in staves[0].findall("./lines/line")]
        if len(lines) != 5:
            raise ValueError("Expected five staff lines")
        elements = list(system.findall("./sig/inters/*"))
        ids = {e.get("id"): e for e in elements}
        alters = {}
        for relation in system.findall("./sig/relations/relation"):
            if relation.find("alter-head") is not None:
                alter = ids[relation.get("source")]
                alters[relation.get("target")] = {"shape": alter.get("shape"), "id": alter.get("id")}
        bars = sorted(xof(e) for e in elements if e.tag == "staff-barline")
        clefs = sorted((e for e in elements if e.tag == "clef"), key=xof)
        keys = sorted((e for e in elements if e.tag == "key"), key=xof)
        heads = sorted((e for e in elements if e.tag == "head"), key=xof)
        changes = sorted([(xof(e), "clef", e.get("kind")) for e in clefs]
                         + [(xof(e), "key", int(e.get("fifths", "0"))) for e in keys])
        ci, previous_measure, state, notes = 0, -1, {}, []
        for number, head in enumerate(heads, 1):
            x, y, width, height = bounds(head)
            cx, cy = x + width / 2, y + height / 2
            measure = sum(b < cx for b in bars)
            if measure != previous_measure:
                state = {}
                previous_measure = measure
            while ci < len(changes) and changes[ci][0] < cx:
                _, kind, value = changes[ci]
                if kind == "clef":
                    clef = value
                else:
                    fifths, state = value, {}
                ci += 1
            if clef not in CLEFS or not -7 <= fifths <= 7:
                raise ValueError("Unsupported OMR clef/key; correct recognition before import")
            staff_pitch = float(head.get("pitch"))
            if not math.isfinite(staff_pitch):
                raise ValueError("Non-finite staff pitch")
            diatonic = CLEFS[clef] - round(staff_pitch)
            step, octave = "CDEFGAB"[diatonic % 7], diatonic // 7
            accidental = alters.get(head.get("id"))
            if accidental:
                if accidental["shape"] not in ACCIDENTALS:
                    raise ValueError(f"Unsupported accidental: {accidental}")
                state[(step, octave)] = ACCIDENTALS[accidental["shape"]]
            key_alter = (1 if step in "FCGDAEB"[:max(0, fifths)] else
                         -1 if step in "BEADGCF"[:max(0, -fifths)] else 0)
            alter = state.get((step, octave), key_alter)
            pitch = step + {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}[alter] + str(octave)
            middle, half_step = staff_geometry(lines, cx)
            grade = float(head.get("grade")) if head.get("grade") is not None else None
            if grade is not None and (not math.isfinite(grade) or not 0 <= grade <= 1):
                raise ValueError("OMR notehead grade must be between 0 and 1")
            notes.append({"id": number, "omr_id": head.get("id"), "x": cx, "y": cy,
                          "box": [x, y, width, height], "pitch": pitch, "clef": clef,
                          "key": fifths, "staff_pitch": staff_pitch,
                          "explicit_accidental": accidental, "measure_local": measure,
                          "grade": grade,
                          "geometry_residual": round((cy - middle) / half_step - staff_pitch, 3)})
        # Clef/key changes on systems without played heads still carry forward.
        for _, kind, value in changes[ci:]:
            if kind == "clef":
                clef = value
            else:
                fifths = value
        systems.append({"system": int(system.get("id")), "lines": lines,
                        "barlines": bars, "notes": notes})
    if not systems or len({s["system"] for s in systems}) != len(systems):
        raise ValueError("Missing or duplicate OMR systems")
    return systems


def apply_corrections(candidates: dict, corrections: dict) -> tuple[dict, list[dict]]:
    pages = deepcopy(candidates["pages"])
    issues = []
    if set(pages) != set(corrections["pages"]):
        raise ValueError("Correction pages must exactly match candidate pages")
    for page, systems in pages.items():
        patches = corrections["pages"][page]
        if set(patches) != {str(s["system"]) for s in systems}:
            raise ValueError(f"Correction systems do not match page {page}")
        for system in systems:
            sid = system["system"]
            patch = patches[str(sid)]
            review = patch.get("review", {})
            reviewed = review.get("status") == "source_checked" and bool(review.get("by")) and bool(review.get("note"))
            if not reviewed:
                issues.append({"kind": "unreviewed_pitch", "page": int(page), "system": sid})
            raw_ids = {n["id"] for n in system["notes"]}
            removed = patch.get("remove", [])
            if removed == "all":
                removed = list(raw_ids)
            replaced = patch.get("replace", {})
            if set(removed) - raw_ids or {int(i) for i in replaced} - raw_ids:
                raise ValueError(f"Unknown correction ID at {page}/{sid}")
            if set(removed) & {int(i) for i in replaced}:
                raise ValueError(f"Cannot replace a removed note at {page}/{sid}")
            if "clef" in patch and patch["clef"] not in CLEFS:
                raise ValueError(f"Unsupported corrected clef at {page}/{sid}")
            if "fifths" in patch and (type(patch["fifths"]) is not int or not -7 <= patch["fifths"] <= 7):
                raise ValueError(f"Unsupported corrected key signature at {page}/{sid}")
            context_override = "clef" in patch or "fifths" in patch
            if (removed or replaced or patch.get("add") or patch.get("all_pitch") or context_override) and not patch.get("reason"):
                raise ValueError(f"Corrections need a reason at {page}/{sid}")
            notes, accidental_state, last_measure, last_key = [], {}, None, None
            for note in system["notes"]:
                raw_pitch = note["pitch"]
                clef = patch.get("clef", note["clef"])
                fifths = patch.get("fifths", note["key"])
                pitch = raw_pitch
                if context_override:
                    if "staff_pitch" not in note or "measure_local" not in note:
                        raise ValueError(f"Context correction needs OMR staff geometry at {page}/{sid}")
                    if note["measure_local"] != last_measure or fifths != last_key:
                        accidental_state = {}
                    last_measure, last_key = note["measure_local"], fifths
                    pitch = pitch_at_staff_position(note["staff_pitch"], clef, fifths,
                                                    note.get("explicit_accidental"), accidental_state)
                if note["id"] in removed:
                    continue
                note["raw_id"], note["raw_pitch"] = note["id"], raw_pitch
                if context_override:
                    note["raw_clef"], note["raw_key"] = note["clef"], note["key"]
                note["pitch"] = patch.get("all_pitch", replaced.get(str(note["id"]), pitch))
                note["clef"] = clef
                note["key"] = fifths
                notes.append(note)
            for addition in patch.get("add", []):
                x, y, pitch = addition["x"], addition["y"], addition["pitch"]
                notes.append({"x": x, "y": y, "pitch": pitch, "raw_id": None,
                              "raw_pitch": None, "manual_addition": True,
                              "clef": addition.get("clef", patch.get("clef", candidates["default_clef"]))})
            notes.sort(key=lambda n: n["x"])
            system.update(notes=notes, review=review, correction_reason=patch.get("reason"))
            for i, note in enumerate(notes, 1):
                midi, diatonic, display = pitch_info(note["pitch"])
                if note["clef"] not in CLEFS:
                    raise ValueError(f"Unknown clef {note['clef']}")
                middle, half_step = staff_geometry(system["lines"], note["x"])
                residual = (note["y"] - middle) / half_step - (CLEFS[note["clef"]] - diatonic)
                note_id = f"p{int(page):04}-s{sid:03}-n{i:04}"
                note.update(id=i, note_id=note_id, page=int(page), system=sid, midi=midi,
                            display_pitch=display, position=POSITIONS.get(midi),
                            review_status="source_checked" if reviewed else "unreviewed",
                            review_geometry_residual=round(residual, 3),
                            audio_time_seconds=None)
                if abs(residual) > .65:
                    issues.append({"kind": "pitch_geometry", "note_id": note_id, "residual": residual})
                if note["position"] is None:
                    issues.append({"kind": "position_outside_basic_chart", "note_id": note_id})
    return pages, issues


def attach_rhythm(pages: dict, rhythm: dict, movements: list[dict]) -> tuple[dict, list[dict]]:
    movement_by_page = {}
    definitions = {}
    meter_changes = {}
    for movement in movements:
        mid = movement["id"]
        if type(mid) is not int or mid in definitions:
            raise ValueError("Movement IDs must be unique integers")
        def meter_ticks(meter):
            if not isinstance(meter, list) or len(meter) != 2:
                raise ValueError("Meter must be [numerator, denominator]")
            numerator, denominator = meter
            if type(numerator) is not int or type(denominator) is not int or min(numerator, denominator) <= 0:
                raise ValueError("Invalid meter")
            bar_ticks = Fraction(numerator * 4 * TPQ, denominator)
            if bar_ticks.denominator != 1:
                raise ValueError("Meter is not representable at 480 ticks per quarter")
            return int(bar_ticks)

        meter_ticks(movement["meter"])
        raw_changes = movement.get("meter_changes", [])
        if not isinstance(raw_changes, list):
            raise ValueError("meter_changes must be a list")
        changes = {}
        for change in raw_changes:
            if not isinstance(change, dict):
                raise ValueError("Each meter change must be an object")
            start, meter = change.get("start"), change.get("meter")
            if (not isinstance(start, list) or len(start) != 2
                    or any(type(value) is not int or value < 1 for value in start)):
                raise ValueError("Meter change start must be [page, system]")
            coordinate = tuple(start)
            if coordinate in changes:
                raise ValueError("Duplicate meter change coordinate")
            meter_ticks(meter)
            changes[coordinate] = meter
        meter_changes[mid] = changes
        definitions[mid] = {**movement, "bar_ticks": meter_ticks(movement["meter"])}
        for page in movement["pages"]:
            if str(page) in movement_by_page:
                raise ValueError("A page cannot belong to two movements in v1")
            movement_by_page[str(page)] = mid
    if set(movement_by_page) != set(pages) or set(rhythm["pages"]) != set(pages):
        raise ValueError("Movement and rhythm pages must exactly cover the selected pages")
    available_systems = {(int(page), system["system"]): movement_by_page[page]
                         for page, systems in pages.items() for system in systems}
    for mid, changes in meter_changes.items():
        if any(available_systems.get(coordinate) != mid for coordinate in changes):
            raise ValueError("Meter changes must start at a selected system in their movement")
    ticks = {m: 0 for m in definitions}
    bars = {m: 0 for m in definitions}
    active_meters = {mid: definition["meter"] for mid, definition in definitions.items()}
    events, issues = [], []
    for page, systems in pages.items():
        mid = movement_by_page[page]
        if set(rhythm["pages"][page]) != {str(s["system"]) for s in systems}:
            raise ValueError(f"Rhythm systems do not match page {page}")
        for system in systems:
            sid = system["system"]
            active_meters[mid] = meter_changes[mid].get((int(page), sid), active_meters[mid])
            numerator, denominator = active_meters[mid]
            bar_ticks = int(Fraction(numerator * 4 * TPQ, denominator))
            entry = rhythm["pages"][page][str(sid)]
            review = entry.get("review", {})
            if not (review.get("status") == "source_checked" and review.get("by") and review.get("note")):
                issues.append({"kind": "unreviewed_rhythm", "page": int(page), "system": sid})
            notes, ni, start = system["notes"], 0, ticks[mid]
            for group, text in enumerate(entry["tokens"].split("|"), 1):
                values = text.strip().split()
                if not values:
                    raise ValueError(f"Empty rhythm at {page}/{sid}/{group}")
                base = {"page": int(page), "system": sid, "movement": mid, "bar": bars[mid] + 1, "group": group}
                if len(values) == 1 and re.fullmatch(r"R[1-9]\d*", values[0]):
                    count = int(values[0][1:])
                    duration = count * bar_ticks
                    events.append({**base, "kind": "rest", "onset_ticks": ticks[mid],
                                   "duration_ticks": duration, "rest_bars": count})
                    ticks[mid] += duration
                    bars[mid] += count
                    continue
                used = 0
                bars[mid] += 1
                for value in values:
                    rest, tie = value.startswith("r"), value.endswith("~")
                    if rest and tie:
                        raise ValueError("A rest cannot be tied")
                    duration = Fraction(value.removeprefix("r").removesuffix("~")) * TPQ
                    if duration <= 0 or duration.denominator != 1:
                        raise ValueError(f"Invalid or unrepresentable duration {value!r}")
                    duration = int(duration)
                    event = {**base, "kind": "rest" if rest else "note", "onset_ticks": ticks[mid], "duration_ticks": duration}
                    if not rest:
                        if ni >= len(notes):
                            raise ValueError(f"Too many rhythm notes at {page}/{sid}/{group}")
                        note = notes[ni]
                        note.update(movement=mid, bar=bars[mid], onset_ticks=ticks[mid], duration_ticks=duration,
                                    duration_quarters=str(Fraction(duration, TPQ)), tie_to_next=tie,
                                    timing_status=review.get("status", "unreviewed"))
                        event.update(note_id=note["note_id"], pitch=note["pitch"], midi=note["midi"], tie_to_next=tie)
                        ni += 1
                    events.append(event)
                    ticks[mid] += duration
                    used += duration
                if used != bar_ticks:
                    raise ValueError(f"Bar mismatch at {page}/{sid}/{group}: {used}/{bar_ticks} ticks")
            if ni != len(notes):
                raise ValueError(f"Rhythm does not cover every note at {page}/{sid}: {ni}/{len(notes)}")
            system.update(movement=mid, onset_ticks=start, duration_ticks=ticks[mid] - start)
    for i, event in enumerate(events):
        if event.get("tie_to_next"):
            following = events[i + 1] if i + 1 < len(events) else {}
            if (following.get("kind") != "note" or following.get("movement") != event["movement"]
                    or following.get("midi") != event["midi"]):
                raise ValueError(f"Invalid tie from {event['note_id']} (pitch, rest or movement boundary)")
            following["tie_from_previous"] = True
    for mid, definition in definitions.items():
        expected = definition.get("expected_written_bars")
        if expected is not None and bars[mid] != expected:
            issues.append({"kind": "bar_count", "movement": mid, "expected": expected, "actual": bars[mid]})
    timing = {"ticks_per_quarter": TPQ, "movement_ticks": ticks, "movement_written_bars": bars,
              "events": events, "repeat_regions": rhythm.get("repeat_regions", []),
              "performance_notes": rhythm.get("performance_notes", [])}
    for mid in definitions:
        for repeats in (False, True):
            playback_events(timing, mid, repeats)  # Validate every playback path before publication.
    return timing, issues


def playback_events(timing: dict, movement: int, repeats: bool) -> list[dict]:
    """Expand disjoint, single-pass repeats and one-group first/second endings.

    Reject nesting/overlap and ambiguous ending coordinates. Written events remain
    immutable. Both repeat policies must have valid ties after expansion.
    """
    source = [e for e in timing["events"] if e["movement"] == movement]
    all_groups = {(e["page"], e["system"], e["group"]): e["movement"] for e in timing["events"]}
    groups = [(e["page"], e["system"], e["group"]) for e in source]
    ends, firsts, covered = {}, set(), set()
    for region in timing.get("repeat_regions", []):
        start, end = tuple(region["start"]), tuple(region["end"])
        if start not in all_groups or end not in all_groups or all_groups[start] != all_groups[end]:
            raise ValueError("Repeat coordinates must exist in one movement")
        if all_groups[start] != movement:
            continue
        a, b = groups.index(start), len(groups) - 1 - groups[::-1].index(end)
        if b < a or covered.intersection(range(a, b + 1)):
            raise ValueError("Nested or overlapping repeats are not supported")
        covered.update(range(a, b + 1))
        first = region.get("first_ending")
        second = region.get("second_ending")
        if bool(first) != bool(second):
            raise ValueError("Both ending coordinates are required")
        if first:
            if tuple(first) != end or b + 1 >= len(groups) or groups[b + 1] != tuple(second):
                raise ValueError("v1 endings must be the final repeated group and its next group")
            firsts.add(tuple(first))
        ends[b] = (a, b, tuple(first) if first else None)
    output, tick = [], 0

    def push(event):
        nonlocal tick
        output.append({**event, "source_onset_ticks": event["onset_ticks"], "play_tick": tick})
        tick += event["duration_ticks"]

    for i, event in enumerate(source):
        if repeats or groups[i] not in firsts:
            push(event)
        if repeats and i in ends:
            a, b, first = ends[i]
            for j in range(a, b + 1):
                if groups[j] != first:
                    push(source[j])
    for i, event in enumerate(output):
        if event.get("tie_to_next"):
            following = output[i + 1] if i + 1 < len(output) else {}
            if following.get("kind") != "note" or following.get("midi") != event["midi"]:
                raise ValueError("Tie crosses an unsupported repeat jump")
        # Recompute links; source-order tie flags do not authorize ties across jumps.
        previous = output[i - 1] if i else {}
        event["tie_from_previous"] = bool(previous.get("tie_to_next"))
    return output
