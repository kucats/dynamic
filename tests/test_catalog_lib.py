import tempfile
import unittest
from pathlib import Path

from tools.catalog_lib import is_sha256, repo_file


class CatalogPathTests(unittest.TestCase):
    def test_accepts_repo_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "public" / "index.html"
            target.parent.mkdir()
            target.write_text("ok", encoding="utf-8")
            self.assertEqual(repo_file(root, "public/index.html"), target.resolve())

    def test_rejects_absolute_and_parent_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for value in ("/tmp/outside", "../outside", "public/../outside", "public\\index.html"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    repo_file(root, value)

    def test_checks_sha256_format(self):
        self.assertTrue(is_sha256("a" * 64))
        self.assertFalse(is_sha256("z" * 64))
        self.assertFalse(is_sha256("a" * 63))


if __name__ == "__main__":
    unittest.main()
