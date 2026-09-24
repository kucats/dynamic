import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/dynamic"))

from common import HORN_KEYS, label, parse_pitch, transpose  # noqa: E402
import validate_reader  # noqa: E402
import validate_score  # noqa: E402


class DynamicReaderTests(unittest.TestCase):
    def test_reader_data_is_valid(self):
        self.assertEqual(validate_reader.main(), 0)

    def test_score_viewer_data_is_valid(self):
        self.assertEqual(validate_score.main(), 0)

    def test_score_overrides(self):
        try:
            from build_score import apply_overrides
        except ImportError:                     # OpenCV / Pillow are only needed for rebuilding
            self.skipTest("build dependencies not installed")
        systems = [dict(y0=0, y1=100, bl=[10.0, 200.0, 400.0]), dict(y0=120, y1=200, bl=[10.0, 50.0, 300.0])]
        out = apply_overrides(systems, {"add": [[0, 300]], "drop": [[1, 52]]})
        self.assertEqual(out[0]["bl"], [10.0, 200.0, 300.0, 400.0])
        self.assertEqual(out[1]["bl"], [10.0, 300.0])
        self.assertEqual(systems[0]["bl"], [10.0, 200.0, 400.0])      # input is not mutated

    def test_horn_transposition_spelling(self):
        L, a, o = parse_pitch("C5")
        self.assertEqual(label(*transpose(L, a, o, *HORN_KEYS["F"]))[:2], ["ファ", 4])
        self.assertEqual(label(*transpose(L, a, o, *HORN_KEYS["D"]))[:2], ["レ", 4])
        L, a, o = parse_pitch("Bb4")
        self.assertEqual(label(L, a, o)[:2], ["シ♭", 4])
        sounding = transpose(L, a, o, *HORN_KEYS["D"])          # Bb4 in D -> C4
        self.assertEqual(label(*sounding)[:2], ["ド", 4])
        self.assertEqual(label(*transpose(*sounding, 4, 7))[:2], ["ソ", 4])   # F-horn reading

    def test_sharp_spelling_survives(self):
        L, a, o = parse_pitch("F#4")
        self.assertEqual(label(*transpose(L, a, o, *HORN_KEYS["F"]))[:2], ["シ", 3])


if __name__ == "__main__":
    unittest.main()
