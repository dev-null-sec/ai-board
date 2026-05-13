from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ai_board.cli import main
from ai_board.store import load_board


class CliTests(unittest.TestCase):
    def test_init_creates_guardrail_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init", "--project-name", "Demo"]), 0)

            expected_paths = [
                ".ai-board/board.json",
                "AGENTS.md",
                "docs/开发规范.md",
                "docs/当前状态.md",
                "docs/决策记录.md",
                "docs/项目方向.md",
                "docs/页面设计.md",
                "docs/项目路线/README.md",
                "docs/计划看板.md",
                "docs/归档计划看板.md",
            ]
            for expected_path in expected_paths:
                self.assertTrue((root / expected_path).exists(), expected_path)

    def test_task_lifecycle_renders_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init", "--project-name", "Demo"]), 0)
            self.assertEqual(main(["--root", str(root), "goal", "Ship demo"]), 0)
            self.assertEqual(main(["--root", str(root), "add", "Build login", "--priority", "P1"]), 0)
            self.assertEqual(main(["--root", str(root), "schedule", "T-0001"]), 0)
            self.assertEqual(
                main(["--root", str(root), "start", "T-0001", "--agent", "agent-a", "--scope", "src/login.py"]),
                0,
            )
            self.assertEqual(
                main(["--root", str(root), "complete", "T-0001", "--verification", "unit test passed"]),
                0,
            )
            self.assertEqual(main(["--root", str(root), "archive", "T-0001"]), 0)

            board = load_board(root)
            self.assertEqual(board["project"]["current_goal"], "Ship demo")
            self.assertEqual(len(board["tasks"]), 0)
            self.assertEqual(board["archive"][0]["status"], "archived")
            self.assertTrue((root / "docs" / "计划看板.md").exists())
            archive_text = (root / "docs" / "归档计划看板.md").read_text(encoding="utf-8")
            self.assertIn("unit test passed", archive_text)

    def test_conflict_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "src"])
            with self.assertRaises(SystemExit):
                main(["--root", str(root), "start", "T-0002", "--agent", "b", "--scope", "src/app.py"])
            main(["--root", str(root), "start", "T-0002", "--agent", "b", "--scope", "src/app.py", "--force"])

            self.assertEqual(main(["--root", str(root), "conflicts"]), 0)
            self.assertEqual(main(["--root", str(root), "conflicts", "--fail-on-conflict"]), 1)
            self.assertEqual(main(["--root", str(root), "locks"]), 0)

    def test_show_outputs_task_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Document API"])
            board_file = root / ".ai-board" / "board.json"
            data = json.loads(board_file.read_text(encoding="utf-8"))
            self.assertEqual(data["tasks"][0]["id"], "T-0001")

    def test_add_stores_richer_task_fields_and_renders_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(
                [
                    "--root",
                    str(root),
                    "add",
                    "Build platform task",
                    "--priority",
                    "P1",
                    "--lane",
                    "平台开发",
                    "--source",
                    "roadmap",
                    "--acceptance",
                    "测试通过",
                    "--acceptance",
                    "页面可用",
                    "--depends-on",
                    "T-0001",
                ]
            )
            main(["--root", str(root), "add", "Write content task", "--priority", "P0", "--lane", "课程内容"])

            board = load_board(root)
            task = board["tasks"][0]
            self.assertEqual(task["lane"], "平台开发")
            self.assertEqual(task["source"], "roadmap")
            self.assertEqual(task["acceptance"], ["测试通过", "页面可用"])
            self.assertEqual(task["depends_on"], ["T-0001"])

            board_text = (root / "docs" / "计划看板.md").read_text(encoding="utf-8")
            self.assertIn("### 平台开发", board_text)
            self.assertIn("### 课程内容", board_text)
            self.assertLess(board_text.index("### 平台开发"), board_text.index("Build platform task"))

    def test_init_keeps_existing_guardrail_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            agents = root / "AGENTS.md"
            agents.write_text("custom rules", encoding="utf-8")

            self.assertEqual(main(["--root", str(root), "init"]), 0)

            self.assertEqual(agents.read_text(encoding="utf-8"), "custom rules")
            self.assertTrue((root / "AGENTS.md.example").exists())

    def test_skills_commands_do_not_require_board(self) -> None:
        self.assertEqual(main(["skills", "list"]), 0)
        self.assertEqual(main(["skills", "get", "core"]), 0)
        self.assertEqual(main(["skills", "get", "core", "--full"]), 0)

    def test_board_renders_tasks_by_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Low priority", "--priority", "P2"])
            main(["--root", str(root), "add", "Urgent priority", "--priority", "P0"])
            main(["--root", str(root), "add", "Normal priority", "--priority", "P1"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "schedule", "T-0003"])

            board_text = (root / "docs" / "计划看板.md").read_text(encoding="utf-8")
            self.assertLess(board_text.index("P0 Urgent priority"), board_text.index("P1 Normal priority"))
            self.assertLess(board_text.index("P1 Normal priority"), board_text.index("P2 Low priority"))

    def test_concurrent_adds_keep_board_valid_and_ids_unique(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)

            commands = [
                [sys.executable, "-m", "ai_board", "--root", str(root), "add", f"Task {index}"]
                for index in range(6)
            ]
            processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for command in commands]
            for process in processes:
                stdout, stderr = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 0, stdout + stderr)

            board = load_board(root)
            ids = [task["id"] for task in board["tasks"]]
            self.assertEqual(len(ids), 6)
            self.assertEqual(len(set(ids)), 6)


if __name__ == "__main__":
    unittest.main()
