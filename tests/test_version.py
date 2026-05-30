from __future__ import annotations

import pathlib
import re
import unittest
from contextlib import redirect_stdout
from io import StringIO

import ai_board
from ai_board.cli import main


class VersionTests(unittest.TestCase):
    def test_package_version_matches_pyproject(self) -> None:
        pyproject = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"
        match = re.search(r'^version = "([^"]+)"$', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(ai_board.__version__, match.group(1))

    def test_short_version_flag_prints_package_version(self) -> None:
        buffer = StringIO()
        with self.assertRaises(SystemExit) as error, redirect_stdout(buffer):
            main(["-v"])
        self.assertEqual(error.exception.code, 0)
        self.assertEqual(buffer.getvalue().strip(), f"ai-board {ai_board.__version__}")

    def test_long_version_flag_prints_package_version(self) -> None:
        buffer = StringIO()
        with self.assertRaises(SystemExit) as error, redirect_stdout(buffer):
            main(["--version"])
        self.assertEqual(error.exception.code, 0)
        self.assertEqual(buffer.getvalue().strip(), f"ai-board {ai_board.__version__}")


if __name__ == "__main__":
    unittest.main()
