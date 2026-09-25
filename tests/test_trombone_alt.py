import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dynamic"))

import trombone_alt as ta  # noqa: E402
from common import TROMBONE_POS  # noqa: E402


def partial_midi(k):
    return 79 if k == 13 else 34 + round(1200 * math.log2(k) / 100)


def ev(midi, t, d=0.125, tie=False, unc="", i=[0]):
    i[0] += 1
    return {"note": {"id": i[0], "mvt": "I", "bar": 1 + int(t), "snd": ["?", 0, midi], "tie": tie, "unc": unc}, "t": t, "d": d}


class TableTest(unittest.TestCase):
    table = ta.load_table()

    def test_standard_matches_reader_positions(self):
        for midi, pos in TROMBONE_POS.items():
            std = [o for o in self.table[midi] if o.get("standard")]
            self.assertEqual(len(std), 1, midi)
            self.assertEqual(std[0]["pos"], pos, midi)
            self.assertEqual(std[0]["cost"], 0)

    def test_options_lie_on_the_harmonic_series(self):
        for midi, opts in self.table.items():
            self.assertEqual(len({o["pos"] for o in opts}), len(opts), midi)
            for o in opts:
                self.assertEqual(partial_midi(o["partial"]) - (o["pos"] - 1), midi, (midi, o))
                self.assertTrue(1 <= o["pos"] <= 7)
                if not o.get("standard"):
                    self.assertGreater(o["cost"], 0)
                    self.assertFalse(o["partial"] == 7 and o["pos"] == 1, "seventh partial cannot be pulled in from 1st")


class SolveTest(unittest.TestCase):
    table = ta.load_table()

    def choose(self, events, lip=1.0):
        return [c["pos"] for c in ta.solve(events, self.table, lip)]

    def test_fast_g_f_g_uses_sixth_position_f(self):
        seq = [55, 53, 55, 53, 55, 53, 55]          # G3 F3 … as fast sixteenths
        events = [ev(m, k * 0.12) for k, m in enumerate(seq)]
        self.assertEqual(self.choose(events), [4, 6, 4, 6, 4, 6, 4])

    def test_slow_notes_keep_standard_positions(self):
        events = [ev(m, k * 2.0, d=1.9) for k, m in enumerate([55, 53, 55])]
        self.assertEqual(self.choose(events), [4, 1, 4])

    def test_lip_weight_moves_the_balance(self):
        seq = [60, 62, 60, 62, 60]                  # C4 D4 alternation: 3-1 (partial 5) vs 3-4 (5→6)
        events = [ev(m, k * 0.12) for k, m in enumerate(seq)]
        self.assertEqual(self.choose(events, lip=ta.PRESETS["lip"]), [3, 1, 3, 1, 3])
        self.assertEqual(self.choose(events, lip=ta.PRESETS["slide"]), [3, 4, 3, 4, 3])

    def test_tie_keeps_the_position(self):
        events = [ev(55, 0.0), ev(53, 0.12), ev(53, 0.24, tie=True), ev(55, 0.36)]
        pos = self.choose(events)
        self.assertEqual(pos[1], pos[2])

    def test_unresolved_notes_get_no_option(self):
        events = [ev(55, 0.0), ev(53, 0.12, unc="pitch"), ev(55, 0.24)]
        self.assertIsNone(ta.solve(events, self.table)[1])

    def test_committed_suggestions_are_current(self):
        self.assertEqual(ta.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
