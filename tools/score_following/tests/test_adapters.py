import json
from pathlib import Path

import pytest
from scorefollow.adapters import ImportError, from_dynamic, from_musicxml
from scorefollow.audio import HOP, StreamingAudio
from scorefollow.fixtures import synthesize
from scorefollow.follower import Follower
from scorefollow.schema import Note, Score


def xml(notes, attributes="", direction=""):
    return f"""<score-partwise><part id="P1"><measure number="1"><attributes><divisions>4</divisions>{attributes}</attributes>{direction}{notes}</measure></part></score-partwise>""".encode()


def note(step="C", octave=4, extra="", duration=4):
    return f"<note>{extra}<pitch><step>{step}</step><octave>{octave}</octave></pitch><duration>{duration}</duration><voice>1</voice></note>"


def test_xml_pitch_transposition_tie_and_rest():
    raw = xml(
        note(extra='<tie type="start"/>')
        + note(extra='<tie type="stop"/>')
        + "<note><rest/><duration>4</duration></note>"
        + note("D"),
        "<transpose><diatonic>-4</diatonic><chromatic>-7</chromatic></transpose>",
    )
    score = from_musicxml(raw)
    assert len(score.events) == 3 and score.events[0].duration == 2
    assert score.concert_pitch(score.events[0]) == 53
    assert score.events[-1].start == 3
    assert score.audit_status == "unreviewed"


@pytest.mark.parametrize(
    "extra", ["<chord/>", "<grace/>", "<cue/>", "<backup/>", "<repeat/>", "<ending/>", "<segno/>"]
)
def test_xml_ambiguous_semantics_rejected(extra):
    with pytest.raises(ImportError):
        from_musicxml(xml(note(extra=extra)))


def test_xml_entities_and_unmatched_ties_rejected():
    with pytest.raises(ImportError):
        from_musicxml(
            b'<!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><score-partwise>&xxe;</score-partwise>'
        )
    with pytest.raises(ImportError):
        from_musicxml(xml(note(extra='<tie type="stop"/>')))
    with pytest.raises(ImportError):
        from_musicxml(xml(note(extra='<tie type="start"/>')))


def dynamic():
    return dict(
        schema=1,
        id="fixture",
        title="Original test",
        part="Horn",
        movements=[dict(key="I", title="First", timeline=[[1, 1, 2, False], [1, 1, 2, True]])],
        systems=[dict(i=0, page=3)],
        notes=[
            dict(
                id=1,
                mvt="I",
                s=0,
                bar=1,
                off=0,
                dur=0.25,
                snd=["C", 4, 60],
                w=["G", 4, 67],
                tie=False,
                unc="",
            )
        ],
    )


def test_dynamic_repeat_identity_unit_conversion_and_no_double_transpose():
    score = from_dynamic(dynamic(), "I")
    assert [n.pitch for n in score.events] == [60, 60]
    assert [n.start for n in score.events] == [0, 4]
    assert [n.occurrence for n in score.events] == [1, 2]
    assert score.events[0].duration == 1 and score.events[0].page == 3
    assert score.events[0].source_id == score.events[1].source_id
    assert score.events[0].event_id != score.events[1].event_id
    assert score.audit_status == "unreviewed"


def test_dynamic_uncertainty_not_silently_played():
    data = dynamic()
    data["notes"][0]["unc"] = "octave unclear"
    with pytest.raises(ImportError):
        from_dynamic(data, "I")


def test_repository_dynamic_reader_data_respects_uncertainty_and_sounding_pitch():
    root = Path(__file__).resolve().parents[3]
    paths = [
        root / "public/reader/data/dvorak8-horn2.json",
        root / "public/reader/data/dvorak8-horn3-mvt3.json",
    ]
    clean, blocked = 0, 0
    for path in paths:
        data = json.loads(path.read_text())
        source_by_id = {str(n["id"]): n for n in data["notes"]}
        for movement in data["movements"]:
            key = movement["key"]
            source = [n for n in data["notes"] if n.get("mvt") == key]
            if any(n.get("unc") for n in source):
                with pytest.raises(ImportError):
                    from_dynamic(data, key)
                blocked += 1
                continue
            score = from_dynamic(data, key)
            clean += 1
            assert score.audit_status == "unreviewed"
            assert score.pitch_domain == "concert"
            assert score.transpose_semitones == 0
            assert all(
                event.pitch is None
                or event.pitch == float(source_by_id[event.source_id]["snd"][2])
                for event in score.events
            )
            assert all(
                left.start + left.duration <= right.start + 1e-7
                for left, right in zip(score.events, score.events[1:])
            )
    # The checked-in reader corpus currently contains both structurally usable
    # movements and movements that must remain blocked by unresolved source notes.
    assert clean >= 3
    assert blocked >= 1


def test_checked_in_dynamic_midscore_phrase_reacquires_from_audio_without_hint():
    root = Path(__file__).resolve().parents[3]
    data = json.loads((root / "public/reader/data/dvorak8-horn3-mvt3.json").read_text())
    full = from_dynamic(data, "III")
    notes = [event for event in full.events if event.pitch is not None]
    width = 10
    patterns = {}
    for i in range(len(notes) - width + 1):
        pattern = tuple(round(n.pitch) for n in notes[i : i + width])
        patterns[pattern] = patterns.get(pattern, 0) + 1
    candidates = []
    for i in range(1, len(notes) - width):
        window = notes[i : i + width]
        pattern = tuple(round(n.pitch) for n in window)
        span = window[-1].start - window[0].start
        if patterns[pattern] == 1 and span <= 64:
            candidates.append((span, i))
    assert candidates, "checked-in movement should expose at least one bounded unique phrase"
    _, start_index = min(candidates)
    window = notes[start_index : start_index + width]
    origin = window[0].start
    fixture = Score(
        title="DYNAMIC checked-in midscore regression excerpt",
        part=full.part,
        audit_status="synthetic",
        provenance="Synthesized only from checked-in reviewed-data candidate pitches; not a real recording",
        tempo_bpm=full.tempo_bpm,
        events=[
            Note(
                event_id=f"fixture-{j}",
                measure=n.measure,
                beat=n.beat,
                start=n.start - origin,
                duration=n.duration,
                pitch=n.pitch,
            )
            for j, n in enumerate(window)
        ],
    )
    audio, _ = synthesize(fixture, noise=0.003, seed=20260924)
    dsp, follower = StreamingAudio(), Follower(full)
    trace = []
    for sample in range(0, len(audio), HOP):
        for observation in dsp.push(audio[sample : sample + HOP], sample):
            trace.append(follower.consume(observation))
    target = window[-1].event_id
    assert any(
        row["status"] == "tracking"
        and row["position"]
        and row["position"]["event_id"] == target
        for row in trace
    ), (start_index, target, trace[-1]["position"], trace[-1]["alternatives"])
