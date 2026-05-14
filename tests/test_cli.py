from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_board import store
from ai_board.cli import main
from ai_board.errors import BoardError
from ai_board.store import load_board, now_iso, save_board


class CliTests(unittest.TestCase):
    def assert_cli_error(self, args: list[str], expected: str = "") -> str:
        output = io.StringIO()
        with redirect_stderr(output):
            self.assertEqual(main(args), 1)
        text = output.getvalue()
        if expected:
            self.assertIn(expected, text)
        return text

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
            self.assertTrue((root / ".ai-board" / "config.json").exists())

    def test_config_controls_default_lane_agent_kind_and_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init", "--project-name", "Demo"]), 0)
            config_file = root / ".ai-board" / "config.json"
            config = json.loads(config_file.read_text(encoding="utf-8"))
            config.update(
                {
                    "default_lane": "Docs",
                    "default_agent_kind": "codex",
                    "default_lease_minutes": 15,
                }
            )
            config_file.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

            self.assertEqual(main(["--root", str(root), "add", "Config task"]), 0)
            claim_output = io.StringIO()
            with redirect_stdout(claim_output):
                self.assertEqual(main(["--root", str(root), "agents", "claim"]), 0)
            self.assertIn("codex-00", claim_output.getvalue())
            self.assertEqual(main(["--root", str(root), "schedule", "T-0001"]), 0)
            self.assertEqual(main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "docs"]), 0)

            board = load_board(root)
            self.assertEqual(board["tasks"][0]["lane"], "Docs")
            self.assertEqual(board["agents"][0]["kind"], "codex")
            self.assertIn("lease_expires_at", board["tasks"][0])

    def test_config_language_controls_rendered_board_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init", "--project-name", "Demo"]), 0)
            config_file = root / ".ai-board" / "config.json"
            config = json.loads(config_file.read_text(encoding="utf-8"))
            config["language"] = "en-US"
            config_file.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

            self.assertEqual(main(["--root", str(root), "add", "Write docs", "--source", "test"]), 0)
            self.assertEqual(main(["--root", str(root), "render"]), 0)

            board_text = (root / "docs" / "计划看板.md").read_text(encoding="utf-8")
            archive_text = (root / "docs" / "归档计划看板.md").read_text(encoding="utf-8")
            self.assertIn("# Planning Board", board_text)
            self.assertIn("## Current Goal", board_text)
            self.assertIn("## Inbox", board_text)
            self.assertIn("| ID | Priority | Task | Owner | Scope | Source |", board_text)
            self.assertIn("# Archived Planning Board", archive_text)

            doctor_output = io.StringIO()
            with redirect_stdout(doctor_output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 0)
            self.assertIn("doctor: ok", doctor_output.getvalue())

    def test_missing_config_keeps_defaults_for_old_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init", "--project-name", "Demo"]), 0)
            (root / ".ai-board" / "config.json").unlink()

            self.assertEqual(main(["--root", str(root), "add", "Old project task"]), 0)
            self.assertEqual(main(["--root", str(root), "agents", "claim"]), 0)

            board = load_board(root)
            self.assertEqual(board["tasks"][0]["lane"], "默认")
            self.assertEqual(board["agents"][0]["id"], "agent-00")

    def test_onboard_initializes_and_classifies_empty_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "onboard", "--init-if-missing", "--project-name", "Demo"]), 0)

            text = output.getvalue()
            self.assertTrue((root / ".ai-board" / "board.json").exists())
            self.assertIn("board: created", text)
            self.assertIn("project_kind: empty", text)
            self.assertIn("docs_need_fill: yes", text)
            self.assertIn("不要直接开始编码", text)

    def test_onboard_classifies_lightweight_and_existing_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "notes.md").write_text("idea", encoding="utf-8")
            (root / "snippet.py").write_text("print('hello')\n", encoding="utf-8")

            lightweight_output = io.StringIO()
            with redirect_stdout(lightweight_output):
                self.assertEqual(main(["--root", str(root), "onboard", "--init-if-missing"]), 0)
            self.assertIn("project_kind: lightweight", lightweight_output.getvalue())

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")

            existing_output = io.StringIO()
            with redirect_stdout(existing_output):
                self.assertEqual(main(["--root", str(root), "onboard", "--init-if-missing"]), 0)
            self.assertIn("project_kind: existing", existing_output.getvalue())
            self.assertIn("pyproject.toml", existing_output.getvalue())

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
            events = self.read_events(root)
            self.assertEqual(
                [event["action"] for event in events],
                ["goal.set", "task.add", "task.schedule", "task.start", "task.complete", "task.archive"],
            )
            self.assertEqual(events[3]["task_id"], "T-0001")
            self.assertEqual(events[3]["agent"], "agent-a")
            self.assertEqual(events[3]["data"]["scope"], ["src/login.py"])

    def test_e2e_real_project_onboarding_lifecycle_doctor_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "pyproject.toml").write_text("[project]\nname = 'sample-app'\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("def main():\n    return 'ok'\n", encoding="utf-8")
            (root / "README.md").write_text("# Sample App\n", encoding="utf-8")

            onboard_output = io.StringIO()
            with redirect_stdout(onboard_output):
                self.assertEqual(main(["--root", str(root), "onboard", "--init-if-missing", "--project-name", "Sample App"]), 0)
            self.assertIn("project_kind: existing", onboard_output.getvalue())

            self.assertEqual(main(["--root", str(root), "goal", "Ship sample app"]), 0)
            self.assertEqual(
                main(
                    [
                        "--root",
                        str(root),
                        "add",
                        "Document startup flow",
                        "--priority",
                        "P1",
                        "--lane",
                        "文档治理",
                        "--source",
                        "e2e",
                        "--acceptance",
                        "README explains startup flow",
                    ]
                ),
                0,
            )
            self.assertEqual(main(["--root", str(root), "schedule", "T-0001"]), 0)
            self.assertEqual(main(["--root", str(root), "agents", "claim", "--kind", "codex"]), 0)
            self.assertEqual(main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "README.md", "src/app.py"]), 0)
            self.assertEqual(main(["--root", str(root), "complete", "T-0001", "--verification", "README and startup code checked", "--leftovers", "无"]), 0)
            self.assertEqual(main(["--root", str(root), "archive", "T-0001"]), 0)

            doctor_output = io.StringIO()
            with redirect_stdout(doctor_output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 0)
            self.assertIn("doctor: ok", doctor_output.getvalue())

            history_output = io.StringIO()
            with redirect_stdout(history_output):
                self.assertEqual(main(["--root", str(root), "history", "T-0001"]), 0)
            history_text = history_output.getvalue()
            self.assertIn("task.start", history_text)
            self.assertIn("task.complete", history_text)
            self.assertIn("task.archive", history_text)

            board = load_board(root)
            self.assertEqual(board["project"]["current_goal"], "Ship sample app")
            self.assertEqual(board["tasks"], [])
            self.assertEqual(board["archive"][0]["status"], "archived")
            self.assertEqual(board["agents"][0]["status"], "idle")
            self.assertIn("Document startup flow", (root / "docs" / "归档计划看板.md").read_text(encoding="utf-8"))

    def test_e2e_multi_agent_collaboration_conflict_release_and_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Build API", "--priority", "P0", "--lane", "平台开发"])
            main(["--root", str(root), "add", "Write docs", "--priority", "P1", "--lane", "文档治理"])
            main(["--root", str(root), "add", "Touch API docs", "--priority", "P1", "--lane", "文档治理"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "schedule", "T-0003"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/api"])

            self.assert_cli_error(["--root", str(root), "start", "T-0002", "--agent", "codex-00", "--scope", "docs"], "busy on T-0001")

            self.assert_cli_error(["--root", str(root), "start", "T-0003", "--agent", "codex-01", "--scope", "src/api/README.md"], "Scope is locked")

            main(["--root", str(root), "start", "T-0002", "--agent", "codex-01", "--scope", "docs"])
            self.assertEqual(main(["--root", str(root), "conflicts", "--fail-on-conflict"]), 0)
            main(["--root", str(root), "complete", "T-0001", "--verification", "API checked", "--leftovers", "无"])

            board = load_board(root)
            agents = {agent["id"]: agent for agent in board["agents"]}
            self.assertEqual(agents["codex-00"]["status"], "idle")
            self.assertEqual(agents["codex-01"]["status"], "busy")

            main(["--root", str(root), "archive", "T-0001"])
            claim_output = io.StringIO()
            with redirect_stdout(claim_output):
                self.assertEqual(main(["--root", str(root), "agents", "claim", "--kind", "codex"]), 0)
            self.assertIn("codex-00 [busy]", claim_output.getvalue())
            main(["--root", str(root), "start", "T-0003", "--agent", "codex-00", "--scope", "src/api/README.md"])
            main(["--root", str(root), "complete", "T-0002", "--verification", "Docs checked", "--leftovers", "无"])
            main(["--root", str(root), "complete", "T-0003", "--verification", "API docs checked", "--leftovers", "无"])
            main(["--root", str(root), "archive", "T-0002"])
            main(["--root", str(root), "archive", "T-0003"])

            doctor_output = io.StringIO()
            with redirect_stdout(doctor_output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 0)
            self.assertIn("doctor: ok", doctor_output.getvalue())
            board = load_board(root)
            self.assertEqual(board["tasks"], [])
            self.assertEqual(len(board["archive"]), 3)
            self.assertTrue(all(agent["status"] == "idle" for agent in board["agents"]))

    def test_status_transitions_reject_invalid_lifecycle_moves(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])

            self.assert_cli_error(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "src/a.py"], "from inbox to active")

            self.assert_cli_error(["--root", str(root), "complete", "T-0001", "--verification", "checked"], "from inbox to done")

            self.assert_cli_error(["--root", str(root), "archive", "T-0001"], "from inbox to archived")

            main(["--root", str(root), "schedule", "T-0001"])
            self.assert_cli_error(["--root", str(root), "complete", "T-0001", "--verification", "checked"], "from scheduled to done")

    def test_block_follows_state_machine_and_releases_active_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/a.py"])
            main(["--root", str(root), "block", "T-0001"])

            board = load_board(root)
            task = board["tasks"][0]
            agent = board["agents"][0]
            self.assertEqual(task["status"], "blocked")
            self.assertEqual(task["lock_owner"], "")
            self.assertEqual(task["lease_expires_at"], "")
            self.assertEqual(agent["status"], "idle")
            self.assertEqual(agent["task_id"], "")

            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/a.py"])
            main(["--root", str(root), "complete", "T-0001", "--verification", "checked"])
            self.assert_cli_error(["--root", str(root), "block", "T-0001"], "from done to blocked")

    def test_conflict_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "src"])
            self.assert_cli_error(["--root", str(root), "start", "T-0002", "--agent", "b", "--scope", "src/app.py"], "Scope is locked")
            main(["--root", str(root), "start", "T-0002", "--agent", "b", "--scope", "src/app.py", "--force"])

            self.assertEqual(main(["--root", str(root), "conflicts"]), 0)
            self.assertEqual(main(["--root", str(root), "conflicts", "--fail-on-conflict"]), 1)
            self.assertEqual(main(["--root", str(root), "locks"]), 0)

    def test_scope_paths_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "schedule", "T-0001"])

            self.assertEqual(main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", r"src\..\docs", "./docs//"]), 0)

            board = load_board(root)
            self.assertEqual(board["tasks"][0]["scope"], ["docs"])

    def test_normalized_scope_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "docs"])

            self.assert_cli_error(["--root", str(root), "start", "T-0002", "--agent", "b", "--scope", "src/../docs/guide.md"], "Scope is locked")

    def test_invalid_scope_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "schedule", "T-0001"])

            self.assert_cli_error(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "../outside"], "Scope cannot leave")
            self.assert_cli_error(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "C:/outside"], "Scope must be relative")

    def test_expired_lock_renew_and_unlock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "src", "--lease-minutes", "1"])

            board = load_board(root)
            board["tasks"][0]["lease_expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(microsecond=0).isoformat()
            save_board(root, board)

            locks_output = io.StringIO()
            with redirect_stdout(locks_output):
                self.assertEqual(main(["--root", str(root), "locks"]), 0)
            self.assertIn("lock=expired", locks_output.getvalue())

            self.assertEqual(main(["--root", str(root), "start", "T-0002", "--agent", "b", "--scope", "src/app.py"]), 0)
            self.assertEqual(main(["--root", str(root), "conflicts", "--fail-on-conflict"]), 0)

            self.assertEqual(main(["--root", str(root), "renew", "T-0001", "--agent", "a", "--lease-minutes", "30"]), 0)
            self.assertEqual(main(["--root", str(root), "conflicts", "--fail-on-conflict"]), 1)

            self.assert_cli_error(["--root", str(root), "unlock", "T-0001", "--agent", "b"], "owned by a")
            self.assertEqual(main(["--root", str(root), "unlock", "T-0001", "--agent", "b", "--force"]), 0)
            self.assertEqual(main(["--root", str(root), "conflicts", "--fail-on-conflict"]), 0)
            board = load_board(root)
            self.assertEqual(board["tasks"][0]["scope"], [])
            self.assertEqual(board["tasks"][0]["lease_expires_at"], "")
            events = self.read_events(root)
            self.assertIn("task.renew", [event["action"] for event in events])
            self.assertIn("task.unlock", [event["action"] for event in events])

    def test_agent_identity_claim_start_and_complete_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])

            claim_output = io.StringIO()
            with redirect_stdout(claim_output):
                self.assertEqual(main(["--root", str(root), "agents", "claim", "--kind", "codex"]), 0)
            self.assertIn("codex-00 [busy]", claim_output.getvalue())

            second_claim_output = io.StringIO()
            with redirect_stdout(second_claim_output):
                self.assertEqual(main(["--root", str(root), "agents", "claim", "--kind", "codex"]), 0)
            self.assertIn("codex-01 [busy]", second_claim_output.getvalue())

            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            self.assertEqual(main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/a.py"]), 0)
            self.assert_cli_error(["--root", str(root), "start", "T-0002", "--agent", "codex-00", "--scope", "src/b.py"], "busy on T-0001")
            self.assertEqual(main(["--root", str(root), "start", "T-0002", "--agent", "codex-01", "--scope", "src/b.py"]), 0)

            board = load_board(root)
            agents = {agent["id"]: agent for agent in board["agents"]}
            self.assertEqual(agents["codex-00"]["task_id"], "T-0001")
            self.assertEqual(agents["codex-01"]["task_id"], "T-0002")

            self.assertEqual(main(["--root", str(root), "complete", "T-0001", "--verification", "checked"]), 0)
            board = load_board(root)
            agents = {agent["id"]: agent for agent in board["agents"]}
            self.assertEqual(agents["codex-00"]["status"], "idle")
            self.assertEqual(agents["codex-00"]["task_id"], "")
            self.assertEqual(agents["codex-01"]["status"], "busy")
            self.assertEqual(board["tasks"][0]["owner_agent"], "codex-00")

            self.assertEqual(main(["--root", str(root), "archive", "T-0001"]), 0)
            board = load_board(root)
            agents = {agent["id"]: agent for agent in board["agents"]}
            self.assertEqual(agents["codex-00"]["status"], "idle")

    def test_expired_agent_identity_can_be_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex", "--lease-minutes", "1"])
            board = load_board(root)
            board["agents"][0]["lease_expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(microsecond=0).isoformat()
            save_board(root, board)

            list_output = io.StringIO()
            with redirect_stdout(list_output):
                self.assertEqual(main(["--root", str(root), "agents", "list"]), 0)
            self.assertIn("codex-00 [expired]", list_output.getvalue())

            claim_output = io.StringIO()
            with redirect_stdout(claim_output):
                self.assertEqual(main(["--root", str(root), "agents", "claim", "--kind", "codex"]), 0)
            self.assertIn("codex-00 [busy]", claim_output.getvalue())

    def test_block_and_agent_release_events_are_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "agents", "release", "codex-00", "--force"])
            main(["--root", str(root), "add", "Blocked task"])
            main(["--root", str(root), "block", "T-0001"])

            events = self.read_events(root)
            actions = [event["action"] for event in events]
            self.assertIn("agents.claim", actions)
            self.assertIn("agents.release", actions)
            self.assertIn("task.block", actions)

    def test_show_outputs_task_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Document API"])
            board_file = root / ".ai-board" / "board.json"
            data = json.loads(board_file.read_text(encoding="utf-8"))
            self.assertEqual(data["tasks"][0]["id"], "T-0001")

    def test_history_outputs_all_events_and_filters_by_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "goal", "Ship demo"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B"])
            main(["--root", str(root), "schedule", "T-0001"])

            all_output = io.StringIO()
            with redirect_stdout(all_output):
                self.assertEqual(main(["--root", str(root), "history"]), 0)
            all_text = all_output.getvalue()
            self.assertIn("goal.set", all_text)
            self.assertIn("task.add", all_text)
            self.assertIn("task=T-0001", all_text)
            self.assertIn("task=T-0002", all_text)

            task_output = io.StringIO()
            with redirect_stdout(task_output):
                self.assertEqual(main(["--root", str(root), "history", "T-0001"]), 0)
            task_text = task_output.getvalue()
            self.assertIn("task=T-0001", task_text)
            self.assertNotIn("task=T-0002", task_text)

    def test_history_handles_missing_or_invalid_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "history", "T-9999"]), 0)
            self.assertIn("no history for T-9999", output.getvalue())

            events_file = root / ".ai-board" / "events.jsonl"
            events_file.write_text("{ broken\n", encoding="utf-8")
            self.assert_cli_error(["--root", str(root), "history"], "Event log is not valid JSONL")

    def test_event_write_failure_does_not_block_board_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            (root / ".ai-board" / "events.jsonl").mkdir()

            self.assertEqual(main(["--root", str(root), "add", "Still recorded in board"]), 0)

            board = load_board(root)
            self.assertEqual(board["tasks"][0]["title"], "Still recorded in board")

    def read_events(self, root: Path) -> list[dict[str, object]]:
        events_file = root / ".ai-board" / "events.jsonl"
        return [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines()]

    def test_add_stores_richer_task_fields_and_renders_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Setup base"])
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
            task = board["tasks"][1]
            self.assertEqual(task["lane"], "平台开发")
            self.assertEqual(task["source"], "roadmap")
            self.assertEqual(task["acceptance"], ["测试通过", "页面可用"])
            self.assertEqual(task["depends_on"], ["T-0001"])

            board_text = (root / "docs" / "计划看板.md").read_text(encoding="utf-8")
            self.assertIn("### 平台开发", board_text)
            self.assertIn("### 课程内容", board_text)
            self.assertIn("| ID | 优先级 | 任务 | 负责人 | Scope | 来源 |", board_text)
            self.assertIn("| `T-0002` | P1 | Build platform task | 未指定 | 未声明 | roadmap |", board_text)
            self.assertIn("**验收 / 依赖**", board_text)
            self.assertIn("  - 测试通过", board_text)
            self.assertIn("- `T-0002` 依赖：T-0001", board_text)
            self.assertLess(board_text.index("### 平台开发"), board_text.index("Build platform task"))

    def test_dependency_validation_blocks_unknown_self_cycle_and_unfinished_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])

            self.assert_cli_error(["--root", str(root), "add", "Task B", "--depends-on", "T-9999"], "Unknown dependency")

            self.assert_cli_error(["--root", str(root), "add", "Task B", "--depends-on", "T-0002"], "cannot depend on itself")

            main(["--root", str(root), "add", "Task B", "--depends-on", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            self.assert_cli_error(["--root", str(root), "start", "T-0002", "--agent", "a", "--scope", "src/b.py"], "dependencies are not complete")

            self.assertEqual(main(["--root", str(root), "start", "T-0002", "--agent", "a", "--scope", "src/b.py", "--force"]), 0)

    def test_dependency_cycle_is_rejected_at_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B", "--depends-on", "T-0001"])
            board = load_board(root)
            board["tasks"][0]["depends_on"] = ["T-0002"]
            save_board(root, board)

            self.assert_cli_error(["--root", str(root), "schedule", "T-0001"], "Dependency cycle")

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
            p0_row = "| `T-0002` | P0 | Urgent priority |"
            p1_row = "| `T-0003` | P1 | Normal priority |"
            p2_row = "| `T-0001` | P2 | Low priority |"
            self.assertLess(board_text.index(p0_row), board_text.index(p1_row))
            self.assertLess(board_text.index(p1_row), board_text.index(p2_row))

    def test_concurrent_adds_keep_board_valid_and_ids_unique(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)

            commands = [
                [sys.executable, "-m", "ai_board", "--root", str(root), "add", f"Task {index}"]
                for index in range(6)
            ]
            processes = [
                subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
                for command in commands
            ]
            for process in processes:
                stdout, stderr = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 0, (stdout or "") + (stderr or ""))

            board = load_board(root)
            ids = [task["id"] for task in board["tasks"]]
            self.assertEqual(len(ids), 6)
            self.assertEqual(len(set(ids)), 6)

    def test_stale_board_lock_with_dead_pid_is_cleared(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)
            lock_file = root / ".ai-board" / "board.lock"
            lock_file.write_text(
                json.dumps({"pid": 999999, "created_at": now_iso(), "command": "old run"}),
                encoding="utf-8",
            )

            self.assertEqual(main(["--root", str(root), "add", "Recovered task"]), 0)

            self.assertFalse(lock_file.exists())
            board = load_board(root)
            self.assertEqual(board["tasks"][0]["title"], "Recovered task")

    def test_load_board_backfills_missing_v1_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            board_dir = root / ".ai-board"
            board_dir.mkdir()
            (board_dir / "board.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "project": {"name": "old"},
                        "next_id": 2,
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                        "tasks": [
                            {
                                "id": "T-0001",
                                "title": "Old task",
                                "priority": "P2",
                                "status": "inbox",
                                "created_at": now_iso(),
                                "updated_at": now_iso(),
                            }
                        ],
                        "archive": [],
                    }
                ),
                encoding="utf-8",
            )

            board = load_board(root)

            self.assertEqual(board["agents"], [])
            self.assertEqual(board["project"]["current_goal"], "")
            task = board["tasks"][0]
            self.assertEqual(task["lane"], "默认")
            self.assertEqual(task["acceptance"], [])
            self.assertEqual(task["depends_on"], [])
            self.assertEqual(task["scope"], [])

    def test_load_board_reports_invalid_json_as_human_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            board_dir = root / ".ai-board"
            board_dir.mkdir()
            (board_dir / "board.json").write_text("{ broken", encoding="utf-8")

            with self.assertRaises(BoardError) as error:
                load_board(root)

            self.assertIn("Board file is not valid JSON", str(error.exception))

    def test_load_board_rejects_invalid_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            board_dir = root / ".ai-board"
            board_dir.mkdir()
            (board_dir / "board.json").write_text(
                json.dumps({"schema_version": 999, "project": {}, "tasks": [], "archive": []}),
                encoding="utf-8",
            )

            with self.assertRaises(BoardError) as error:
                load_board(root)

            self.assertIn("Unsupported board schema_version", str(error.exception))

    def test_stale_board_lock_with_old_timestamp_is_cleared(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)
            lock_file = root / ".ai-board" / "board.lock"
            old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(microsecond=0).isoformat()
            lock_file.write_text(
                json.dumps({"pid": 0, "created_at": old_time, "command": "crashed run"}),
                encoding="utf-8",
            )

            self.assertEqual(main(["--root", str(root), "add", "Recovered by timestamp"]), 0)

            self.assertFalse(lock_file.exists())
            board = load_board(root)
            self.assertEqual(board["tasks"][0]["title"], "Recovered by timestamp")

    def test_busy_stale_board_lock_cleanup_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)
            lock_file = root / ".ai-board" / "board.lock"
            old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(microsecond=0).isoformat()
            lock_file.write_text(
                json.dumps({"pid": 0, "created_at": old_time, "command": "busy stale lock"}),
                encoding="utf-8",
            )
            original_unlink = Path.unlink

            def locked_unlink(path: Path, *args: object, **kwargs: object) -> None:
                if path == lock_file:
                    raise PermissionError("locked")
                original_unlink(path, *args, **kwargs)

            try:
                Path.unlink = locked_unlink  # type: ignore[method-assign]
                self.assertFalse(store.clear_stale_lock(lock_file))
            finally:
                Path.unlink = original_unlink  # type: ignore[method-assign]

            self.assertTrue(lock_file.exists())

    def test_doctor_reports_stale_board_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)
            lock_file = root / ".ai-board" / "board.lock"
            old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(microsecond=0).isoformat()
            lock_file.write_text(
                json.dumps({"pid": 0, "created_at": old_time, "command": "crashed run"}),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "doctor"]), 0)
            self.assertIn("stale board lock", output.getvalue())

            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)

    def test_doctor_reports_stale_generated_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)
            (root / "docs" / "计划看板.md").write_text("stale", encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            self.assertIn("generated doc stale", output.getvalue())
            self.assertIn("ai-board render", output.getvalue())

    def test_doctor_reports_active_task_and_agent_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)
            board = load_board(root)
            board["tasks"].append(
                {
                    "id": "T-0001",
                    "title": "Broken active",
                    "priority": "P2",
                    "status": "active",
                    "lane": "默认",
                    "owner_agent": "codex-00",
                    "scope": [],
                    "depends_on": [],
                    "acceptance": [],
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
            board["agents"].append(
                {
                    "id": "codex-00",
                    "kind": "codex",
                    "status": "busy",
                    "task_id": "T-9999",
                    "lease_expires_at": "",
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
            save_board(root, board)

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            text = output.getvalue()
            self.assertIn("active task T-0001 has no scope", text)
            self.assertIn("agent codex-00 points to T-9999", text)

    def test_doctor_reports_bad_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)
            (root / ".ai-board" / "events.jsonl").write_text("{ broken\n", encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            self.assertIn("event log", output.getvalue())


if __name__ == "__main__":
    unittest.main()
