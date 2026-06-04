from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_board.cli import main
from ai_board.gate import evaluate_scope_gate, parse_name_status, read_staged_diff_paths, split_business_paths
from ai_board.store import find_task, load_board, save_board


class ScopeGateTests(unittest.TestCase):
    def init_root(self, root: Path, mode: str = "required") -> None:
        self.assertEqual(main(["--root", str(root), "init", "--project-name", "Gate Demo"]), 0)
        self.assertEqual(main(["--root", str(root), "config", "set", "scope_gate", mode]), 0)

    def start_task(self, root: Path, scope: list[str]) -> None:
        self.assertEqual(main(["--root", str(root), "agents", "claim", "--kind", "codex"]), 0)
        self.assertEqual(main(["--root", str(root), "add", "Gate task", "--acceptance", "checked"]), 0)
        self.assertEqual(main(["--root", str(root), "schedule", "T-0001"]), 0)
        self.assertEqual(main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", *scope]), 0)

    def test_parse_name_status_includes_rename_and_delete_paths(self) -> None:
        output = "A\tREADME.md\nM\tsrc/app.py\nD\tsrc/old.py\nR100\tsrc/old.py\tsrc/new.py\nC100\tdocs/a.md\tdocs/b.md\n"
        self.assertEqual(
            parse_name_status(output),
            ["README.md", "src/app.py", "src/old.py", "src/old.py", "src/new.py", "docs/a.md", "docs/b.md"],
        )

    def test_bookkeeping_paths_are_ignored(self) -> None:
        checked, ignored = split_business_paths([".ai-board/board.json", "docs/计划看板.md", "src/app.py"])
        self.assertEqual(checked, ["src/app.py"])
        self.assertEqual(ignored, [".ai-board/board.json", "docs/计划看板.md"])

    def test_required_gate_fails_business_paths_without_active_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.init_root(root)

            result = evaluate_scope_gate(root, ["src/app.py"])

            self.assertEqual(result.mode, "required")
            self.assertEqual(result.uncovered_paths, ["src/app.py"])
            self.assertEqual(result.exit_code, 1)

    def test_suggest_gate_reports_but_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.init_root(root, mode="suggest")

            result = evaluate_scope_gate(root, ["src/app.py"])

            self.assertEqual(result.uncovered_paths, ["src/app.py"])
            self.assertEqual(result.exit_code, 0)

    def test_off_gate_skips_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.init_root(root, mode="off")

            result = evaluate_scope_gate(root, ["src/app.py"])

            self.assertEqual(result.mode, "off")
            self.assertEqual(result.checked_paths, [])
            self.assertEqual(result.exit_code, 0)

    def test_active_scope_covers_subpaths_but_not_sibling_prefixes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.init_root(root)
            self.start_task(root, ["src/api"])

            covered = evaluate_scope_gate(root, ["src/api/handler.py"])
            uncovered = evaluate_scope_gate(root, ["src/apix/handler.py"])

            self.assertEqual(covered.uncovered_paths, [])
            self.assertEqual(covered.exit_code, 0)
            self.assertEqual(uncovered.uncovered_paths, ["src/apix/handler.py"])
            self.assertEqual(uncovered.exit_code, 1)

    def test_root_scope_covers_every_business_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.init_root(root)
            self.start_task(root, ["."])

            result = evaluate_scope_gate(root, ["README.md", "src/app.py", "docs/guide.md"])

            self.assertEqual(result.uncovered_paths, [])
            self.assertEqual(result.exit_code, 0)

    def test_expired_active_task_scope_does_not_cover_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.init_root(root)
            self.start_task(root, ["src"])
            board = load_board(root)
            task = find_task(board, "T-0001")
            task["lease_expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(microsecond=0).isoformat()
            save_board(root, board)

            result = evaluate_scope_gate(root, ["src/app.py"])

            self.assertEqual(result.uncovered_paths, ["src/app.py"])

    def test_only_bookkeeping_paths_pass_without_active_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.init_root(root)

            result = evaluate_scope_gate(root, [".ai-board/board.json", ".ai-board/events.jsonl", "docs/归档计划看板.md"])

            self.assertEqual(result.checked_paths, [])
            self.assertEqual(result.ignored_paths, [".ai-board/board.json", ".ai-board/events.jsonl", "docs/归档计划看板.md"])
            self.assertEqual(result.exit_code, 0)

    @unittest.skipIf(shutil.which("git") is None, "git is not available")
    def test_read_staged_diff_paths_reads_git_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "-C", str(root), "init"], capture_output=True, check=True)
            (root / "README.md").write_text("hello\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], capture_output=True, check=True)

            self.assertEqual(read_staged_diff_paths(root), ["README.md"])


if __name__ == "__main__":
    unittest.main()
