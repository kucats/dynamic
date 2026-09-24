"""Check the horn fingering aid (public/reader/horn-fingerings.json) against the harmonic series.

Pitches are MIDI numbers of the F-horn written reading. A fingering is valid when the written pitch
plus the semitones its valves lower reaches an open partial of that side. The 7th partial (flat)
is accepted only as an alternate, never as the first choice.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART = json.loads((ROOT / "public/reader/horn-fingerings.json").read_text(encoding="utf-8"))

# open partials 2..16 written for horn in F (fundamental C2 = 36); the B♭ side sits a perfect fourth higher
PARTIAL_OFFSETS = {2: 12, 3: 19, 4: 24, 5: 28, 6: 31, 7: 34, 8: 36, 9: 38, 10: 40, 12: 43, 15: 47, 16: 48}
OPEN = {
    "F": {36 + off: n for n, off in PARTIAL_OFFSETS.items()},
    "Bb": {41 + off: n for n, off in PARTIAL_OFFSETS.items()},
}


def lowered(fingering: str) -> int:
    return 0 if fingering == "0" else sum(CHART["valves"][v] for v in fingering)


class HornFingeringTests(unittest.TestCase):
    def test_fingerings_reach_open_partials(self):
        for side, table in CHART["sides"].items():
            for midi, fingerings in table.items():
                self.assertTrue(fingerings, f"{side} {midi}: empty")
                for rank, f in enumerate(fingerings):
                    self.assertRegex(f, r"^(0|1?2?3?)$", f"{side} {midi}: {f}")
                    partial = OPEN[side].get(int(midi) + lowered(f))
                    self.assertIsNotNone(partial, f"{side} {CHART['names'][midi]} {f}: no open partial")
                    if rank == 0:
                        self.assertNotEqual(partial, 7, f"{side} {CHART['names'][midi]}: flat 7th partial as first choice")

    def test_switch_range_is_covered(self):
        F, Bb = CHART["sides"]["F"], CHART["sides"]["Bb"]
        lo = min(CHART["switch"]["choices"])
        self.assertIn(CHART["switch"]["default"], CHART["switch"]["choices"])
        for midi in range(int(min(F, key=int)), lo):
            self.assertIn(str(midi), F)
        for midi in range(lo, int(max(Bb, key=int)) + 1):
            self.assertIn(str(midi), Bb)
            self.assertIn(str(midi), F)

    def test_123_only_without_alternative(self):
        F, Bb = CHART["sides"]["F"], CHART["sides"]["Bb"]
        for side, table in CHART["sides"].items():
            for midi, fingerings in table.items():
                if "123" in fingerings:
                    self.assertEqual(fingerings, ["123"], f"{side} {CHART['names'][midi]}: 123 listed beside another fingering")
        for midi, fingerings in F.items():
            if fingerings == ["123"] and int(midi) >= 48:
                self.assertIn(midi, Bb, f"{CHART['names'][midi]}: 123 without a B♭-side alternative")

    def test_every_horn_note_has_a_fingering(self):
        parts = json.loads((ROOT / "public/reader/parts.json").read_text(encoding="utf-8"))["parts"]
        for entry in parts:
            data = json.loads((ROOT / "public" / entry["data"]).read_text(encoding="utf-8"))
            if data.get("instrument", "horn") != "horn":
                continue
            for n in data["notes"]:
                self.assertIn(str(n["f"][2]), CHART["sides"]["F"], f"{entry['id']} note {n['id']}")


if __name__ == "__main__":
    unittest.main()
