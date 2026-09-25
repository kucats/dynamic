"""Check the horn fingering aid (public/reader/horn-fingerings.json) against the harmonic series.

Pitches are MIDI numbers of the F-horn written reading. A fingering is valid when the written pitch
plus the semitones its valves lower reaches an open partial of that side. The 7th partial (flat)
is accepted only as an alternate, never as the first choice.

The full-double first choices are also pinned to the Yamaha 楽器解体全書 chart (F/B♭フルダブル row,
read 2026-09-24), which the GONLOG chart agrees with from C4 up.
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


# Yamaha full-double first choice per F-horn written pitch (leading 0 = thumb lever / B♭ side)
YAMAHA_DOUBLE = {
    42: "123", 43: "13", 44: "23", 45: "12", 46: "1", 47: "2", 48: "0", 49: "023", 50: "012", 51: "01",
    52: "02", 53: "00", 54: "2", 55: "0", 56: "23", 57: "12", 58: "1", 59: "2", 60: "0", 61: "12",
    62: "1", 63: "2", 64: "0", 65: "1", 66: "2", 67: "0", 68: "23", 69: "012", 70: "01", 71: "02",
    72: "00", 73: "023", 74: "012", 75: "01", 76: "02", 77: "00", 78: "02", 79: "00", 80: "023",
    81: "012", 82: "01", 83: "02", 84: "00",
}


def first_choice(midi: int, mode: str = "double", switch: int | None = None) -> str:
    """Mirror of fingering() in public/reader/app.js (first choice only)."""
    F, B = CHART["sides"]["F"].get(str(midi), []), CHART["sides"]["Bb"].get(str(midi), [])
    if mode != "double" or not B:
        return F[0]
    sw = CHART["switch"]["default"] if switch is None else switch
    low, keep_f = CHART["double"]["lowBb"], CHART["double"]["mostlyBbKeepF"]
    pick_b = midi not in keep_f if sw == 0 else midi >= sw or low[0] <= midi <= low[1]
    use_b = F[0] == "123" or (pick_b and B[0] != "123")
    return "0" + B[0] if use_b else F[0]


def lowered(fingering: str) -> int:
    return 0 if fingering == "0" else sum(CHART["valves"][v] for v in fingering)


class HornFingeringTests(unittest.TestCase):
    def test_fingerings_reach_open_partials(self):
        for side, table in CHART["sides"].items():
            for midi, fingerings in table.items():
                self.assertTrue(fingerings, f"{side} {midi}: empty")
                self.assertEqual(len(fingerings), len(set(fingerings)), f"{side} {midi}: duplicate fingering")
                for rank, f in enumerate(fingerings):
                    self.assertRegex(f, r"^(0|1?2?3?)$", f"{side} {midi}: {f}")
                    partial = OPEN[side].get(int(midi) + lowered(f))
                    self.assertIsNotNone(partial, f"{side} {CHART['names'][midi]} {f}: no open partial")
                    if rank == 0:
                        self.assertNotEqual(partial, 7, f"{side} {CHART['names'][midi]}: flat 7th partial as first choice")

    def test_switch_range_is_covered(self):
        F, Bb = CHART["sides"]["F"], CHART["sides"]["Bb"]
        lo = CHART["double"]["lowBb"][0]
        self.assertIn(CHART["switch"]["default"], CHART["switch"]["choices"])
        self.assertTrue(all(c == 0 or c > CHART["double"]["lowBb"][1] for c in CHART["switch"]["choices"]))
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

    def test_default_double_matches_yamaha(self):
        for midi, expected in YAMAHA_DOUBLE.items():
            self.assertEqual(first_choice(midi), expected, CHART["names"][str(midi)])

    def test_mostly_bb_mode_keeps_c_and_b_on_f(self):
        for midi in range(49, 85):
            got = first_choice(midi, switch=0)
            # B♭-side codes carry a leading 0 (thumb lever) plus valve digits; an F-side open is the lone "0".
            on_bb = got.startswith("0") and len(got) > 1
            if midi in (54, 59, 60, 71, 72):
                self.assertFalse(on_bb, CHART["names"][str(midi)])
            else:
                self.assertTrue(on_bb, CHART["names"][str(midi)])

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
