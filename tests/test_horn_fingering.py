"""Check the horn fingering chart (public/reader/horn-fingerings.json) against the harmonic series.

The chart transcribes Yamaha's published horn fingering chart; this test guards against
transcription slips. Pitches are MIDI numbers of the F-horn written reading. A fingering is valid
when the written pitch plus the semitones its valves lower reaches an open partial of that side
(T = thumb, B♭ side). The flat 7th and 14th partials are accepted only as alternates.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART = json.loads((ROOT / "public/reader/horn-fingerings.json").read_text(encoding="utf-8"))

# open partials 1..16 written for horn in F (fundamental C2 = 36); the B♭ side sits a perfect fourth higher
PARTIAL_OFFSETS = {1: 0, 2: 12, 3: 19, 4: 24, 5: 28, 6: 31, 7: 34, 8: 36, 9: 38, 10: 40, 12: 43, 14: 46, 15: 47, 16: 48}
OPEN = {
    "F": {36 + off: n for n, off in PARTIAL_OFFSETS.items()},
    "Bb": {41 + off: n for n, off in PARTIAL_OFFSETS.items()},
}
FLAT = {7, 14}


def partial(midi: int, fingering: str):
    side, valves = ("Bb", fingering[1:]) if fingering.startswith("T") else ("F", fingering)
    lowered = 0 if valves == "0" else sum(CHART["valves"][v] for v in valves)
    return OPEN[side].get(midi + lowered)


class HornFingeringTests(unittest.TestCase):
    def check_table(self, name, table, thumb):
        for midi, fingerings in table.items():
            label = f"{name} {CHART['names'][midi]}"
            self.assertTrue(fingerings, f"{label}: empty")
            self.assertEqual(len(fingerings), len(set(fingerings)), f"{label}: duplicate")
            for rank, f in enumerate(fingerings):
                self.assertRegex(f, r"^T?(0|1?2?3?)$" if thumb else r"^(0|1?2?3?)$", f"{label}: {f}")
                p = partial(int(midi), f)
                self.assertIsNotNone(p, f"{label} {f}: no open partial")
                if rank == 0:
                    self.assertNotIn(p, FLAT, f"{label}: flat partial as first choice")

    def test_single_f_reaches_open_partials(self):
        self.check_table("F single", CHART["single_F"], thumb=False)

    def test_double_reaches_open_partials(self):
        self.check_table("double", CHART["double"], thumb=True)

    def test_same_pitches_and_switch_choices(self):
        self.assertEqual(set(CHART["single_F"]), set(CHART["double"]))
        for m in CHART["switch_choices"]:
            self.assertIn(str(m), CHART["double"])

    def test_123_only_without_alternative(self):
        for name in ("single_F", "double"):
            for midi, fingerings in CHART[name].items():
                if "123" in fingerings:
                    self.assertEqual(fingerings, ["123"], f"{name} {CHART['names'][midi]}: 123 beside another fingering")

    def test_spot_values_from_yamaha_chart(self):
        d, f = CHART["double"], CHART["single_F"]
        self.assertEqual(d["69"], ["T12"])            # A4
        self.assertEqual(d["68"], ["23", "T23"])      # G♯4: F side first
        self.assertEqual(d["52"], ["T2", "12"])       # E3: B♭ side first
        self.assertEqual(d["74"], ["T12", "T3"])      # D5
        self.assertEqual(f["73"], ["2", "12"])        # C♯5 on single F

    def test_every_horn_note_has_a_fingering(self):
        parts = json.loads((ROOT / "public/reader/parts.json").read_text(encoding="utf-8"))["parts"]
        for entry in parts:
            data = json.loads((ROOT / "public" / entry["data"]).read_text(encoding="utf-8"))
            if data.get("instrument", "horn") != "horn":
                continue
            for n in data["notes"]:
                self.assertIn(str(n["f"][2]), CHART["double"], f"{entry['id']} note {n['id']}")


if __name__ == "__main__":
    unittest.main()
