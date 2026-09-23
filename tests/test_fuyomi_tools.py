import unittest
from unittest.mock import patch

from tools.fuyomi import publish, score_reading


class FuyomiWrapperTests(unittest.TestCase):
    @patch("tools.fuyomi.score_reading.cli.main")
    def test_score_wrapper_calls_the_local_engine(self, main):
        main.return_value = 7
        self.assertEqual(score_reading.main(["review", "workspace with spaces"]), 7)
        main.assert_called_once_with(["fuyomi", "review", "workspace with spaces"])

    @patch("tools.fuyomi.publish.subprocess.run")
    def test_publish_build_runs_shared_builder_then_validator(self, run):
        run.return_value.returncode = 0
        self.assertEqual(publish.main(["build"]), 0)
        self.assertEqual(run.call_count, 2)
        build_argv, build_kwargs = run.call_args_list[0]
        validate_argv, validate_kwargs = run.call_args_list[1]
        self.assertTrue(build_argv[0][1].endswith("tools/build_catalog.py"))
        self.assertTrue(validate_argv[0][1].endswith("tools/validate_catalog.py"))
        self.assertEqual(build_kwargs["cwd"], publish.ROOT)
        self.assertEqual(validate_kwargs["cwd"], publish.ROOT)
        self.assertNotIn("shell", build_kwargs)
        self.assertNotIn("shell", validate_kwargs)

    @patch("tools.fuyomi.publish.subprocess.run")
    def test_publish_stops_after_failed_builder(self, run):
        run.return_value.returncode = 3
        self.assertEqual(publish.main(["build"]), 3)
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
