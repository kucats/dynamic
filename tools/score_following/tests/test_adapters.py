import pytest
from scorefollow.adapters import ImportError, from_dynamic, from_musicxml


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
