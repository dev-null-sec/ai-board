from __future__ import annotations

import pathlib
import re
import unittest

import ai_board


class VersionTests(unittest.TestCase):
    def test_package_version_matches_pyproject(self) -> None:
        pyproject = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"
        match = re.search(r'^version = "([^"]+)"$', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(ai_board.__version__, match.group(1))


if __name__ == "__main__":
    unittest.main()
