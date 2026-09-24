"""Fail-closed importers. Parsing or successful following never constitutes an audit."""

from __future__ import annotations

import hashlib
from collections import Counter

from defusedxml import ElementTree as ET

from .schema import Note, Score


class ImportError(ValueError):
    """Unsupported or ambiguous score semantics; fix upstream rather than guess."""


def from_dynamic(data: dict, movement: str) -> Score:
    """Import a single movement from the existing DYNAMIC reader schema=1.

    Reader durations/offsets/meters are whole-note units; this protocol uses quarters.
    Reader snd[2] is ALREADY sounding MIDI. Timeline order expands repeat occurrences.
    A tie continuation extends the preceding event; its first source anchor is retained.
    """
    if data.get("schema") != 1:
        raise ImportError("unsupported DYNAMIC reader schema")
    movements = [m for m in data.get("movements", []) if m.get("key") == movement]
    if len(movements) != 1:
        raise ImportError("select exactly one existing movement")
    meta = movements[0]
    timeline = meta.get("timeline", [])
    if not timeline or len(timeline) > 4096:
        raise ImportError("missing or oversized unfolded timeline")
    source = [n for n in data.get("notes", []) if n.get("mvt") == movement]
    if not source or len(source) > 4096:
        raise ImportError("missing or oversized note list")
    systems = {x["i"]: x for x in data.get("systems", [])}
    ids, events, seen = set(), [], Counter()
    for n in source:
        if n["id"] in ids:
            raise ImportError("duplicate source note ID")
        ids.add(n["id"])
        if n.get("unc"):
            raise ImportError("unresolved source note: review upstream before importing")
    cursor = 0.0
    for row in timeline:
        if len(row) != 4:
            raise ImportError("invalid timeline row")
        bar, whole_length, seconds_per_whole, _repeat_marker = row
        length = float(whole_length) * 4
        if not 0 < length <= 256 or not 0 < float(seconds_per_whole) < 60:
            raise ImportError("invalid meter or tempo")
        for n in sorted((n for n in source if n["bar"] == bar), key=lambda n: (n["off"], n["id"])):
            offset, duration = float(n["off"]) * 4, float(n["dur"]) * 4
            if offset < 0 or duration <= 0 or offset + duration > length + 1e-6:
                raise ImportError("note extends outside its source bar")
            sounding = n.get("snd")
            if not isinstance(sounding, list) or len(sounding) != 3:
                raise ImportError("sounding pitch snd[2] required; do not guess transposition")
            pitch = float(sounding[2])
            start = cursor + offset
            if n.get("tie"):
                if (
                    not events
                    or events[-1].pitch != pitch
                    or abs(events[-1].start + events[-1].duration - start) > 1e-6
                ):
                    raise ImportError("tie continuation does not match preceding pitch/duration")
                events[-1] = events[-1].model_copy(update={"duration": events[-1].duration + duration})
                if events[-1].duration > 256:
                    raise ImportError("merged tie too long")
                continue
            seen[n["id"]] += 1
            source_id = str(n["id"])
            events.append(
                Note(
                    event_id=f"{movement}-n{source_id}-o{seen[n['id']]}",
                    source_id=source_id,
                    occurrence=seen[n["id"]],
                    measure=str(bar),
                    beat=offset + 1,
                    start=start,
                    duration=duration,
                    pitch=pitch,
                    page=systems.get(n["s"], {}).get("page"),
                    anchor=f"dynamic:{data.get('id', 'part')}:{source_id}",
                )
            )
        cursor += length
    return Score(
        title=f"{data.get('title', 'DYNAMIC')} / {meta.get('title', movement)}"[:200],
        part=str(data.get("part", "Solo"))[:100],
        audit_status="unreviewed",
        provenance=f"DYNAMIC import; source SHA256={data.get('source', {}).get('sha256', 'unknown')}; not an independent audit"[
            :300
        ],
        tempo_bpm=240 / float(timeline[0][2]),
        pitch_domain="concert",
        events=events,
    )


def from_musicxml(raw: bytes, part_id: str | None = None) -> Score:
    """A deliberately narrow, safe MusicXML partwise, single-voice importer.

    Repeats/jumps/endings, backup/forward, chords, grace/cue notes, microtonal pitches,
    unpitched notes and tempo changes are rejected. Supply a pre-expanded JSON score
    for those cases. XML external entities and DTDs are forbidden, never fetched.
    """
    if len(raw) > 2 * 1024 * 1024:
        raise ImportError("MusicXML exceeds 2 MiB")
    try:
        root = ET.fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except Exception as exc:
        raise ImportError("unsafe or malformed MusicXML") from exc
    # Strip namespace only, not semantics.
    for e in root.iter():
        e.tag = e.tag.split("}")[-1]
    if root.tag != "score-partwise":
        raise ImportError("only score-partwise supported")
    parts = root.findall("part")
    if part_id:
        parts = [p for p in parts if p.get("id") == part_id]
    if len(parts) != 1:
        raise ImportError("select exactly one part with --part-id")
    part = parts[0]
    forbidden = {
        "backup",
        "forward",
        "chord",
        "grace",
        "cue",
        "unpitched",
        "repeat",
        "ending",
        "segno",
        "coda",
        "senza-misura",
        "multiple-rest",
        "measure-repeat",
    }
    if any(e.tag in forbidden for e in part.iter()):
        raise ImportError(
            "unsupported polyphony, cues, measure shorthand, or repeats; expand/review upstream"
        )
    events, divisions, absolute, transpose = [], 1.0, 0.0, 0
    voice, tempo, pending_tie = None, None, False
    pitch_steps = dict(C=0, D=2, E=4, F=5, G=7, A=9, B=11)
    for measure in part.findall("measure"):
        for sound in measure.findall(".//sound"):
            if set(sound.attrib) - {"tempo", "dynamics"}:
                raise ImportError("unsupported sound navigation attributes")
            if sound.get("tempo"):
                value = float(sound.get("tempo"))
                if tempo is not None and tempo != value:
                    raise ImportError("tempo changes require expanded JSON score")
                tempo = value
        if measure.findall(".//metronome") and not measure.findall(".//sound[@tempo]"):
            raise ImportError("metronome without numeric sound tempo is unsupported")
        for attrs in measure.findall("attributes"):
            div = attrs.findtext("divisions")
            if div:
                divisions = float(div)
                if divisions <= 0:
                    raise ImportError("invalid divisions")
            tr = attrs.find("transpose")
            if tr is not None:
                value = int(tr.findtext("chromatic", "0")) + 12 * int(tr.findtext("octave-change", "0"))
                if events and value != transpose:
                    raise ImportError("mid-piece transposition changes require concert JSON")
                if tr.find("double") is not None:
                    raise ImportError("double transposition unsupported")
                transpose = value
        offset = 0.0
        for n in measure.findall("note"):
            v = n.findtext("voice", "1")
            if voice is not None and voice != v:
                raise ImportError("multiple voices are not supported")
            voice = v
            duration = float(n.findtext("duration", "0")) / divisions
            if duration <= 0:
                raise ImportError("missing or nonpositive note duration")
            pitch = None
            p = n.find("pitch")
            if p is not None:
                alter = float(p.findtext("alter", "0"))
                if not alter.is_integer():
                    raise ImportError("microtonal alter requires explicit JSON")
                step, octave = p.findtext("step"), int(p.findtext("octave", "-10"))
                if step not in pitch_steps:
                    raise ImportError("invalid pitch step")
                pitch = 12 * (octave + 1) + pitch_steps[step] + alter
            elif n.find("rest") is None:
                raise ImportError("note needs pitch or rest")
            ties = {t.get("type") for t in n.findall("tie")}
            if ties - {"start", "stop"}:
                raise ImportError("unsupported tie type")
            if "stop" in ties:
                if not pending_tie or pitch is None or not events or events[-1].pitch != pitch:
                    raise ImportError("unmatched tie stop")
                events[-1] = events[-1].model_copy(update={"duration": events[-1].duration + duration})
            else:
                if pending_tie:
                    raise ImportError("unmatched tie start")
                events.append(
                    Note(
                        event_id=f"xml-{len(events)}",
                        measure=measure.get("number", "1"),
                        start=absolute + offset,
                        beat=offset + 1,
                        duration=duration,
                        pitch=pitch,
                    )
                )
            pending_tie = "start" in ties
            offset += duration
        absolute += offset
    if pending_tie:
        raise ImportError("unfinished tie")
    # Re-validation catches overlong merged ties; model_copy itself does not validate.
    return Score.model_validate(
        dict(
            title=root.findtext("work/work-title", "MusicXML import")[:200],
            part=str(part.get("id", "Solo")),
            events=[n.model_dump() for n in events],
            pitch_domain="written",
            transpose_semitones=transpose,
            tempo_bpm=tempo or 100,
            audit_status="unreviewed",
            provenance=f"MusicXML SHA256={hashlib.sha256(raw).hexdigest()}; no note audit",
        )
    )
