from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_board import onboarding, store
from ai_board.cli import main
from ai_board.errors import BoardError
from ai_board.operations import record_verification_evidence, scopes_overlap
from ai_board.store import find_task, load_board, load_config, now_iso, read_events, save_board


class CliTests(unittest.TestCase):
    @contextmanager
    def cli_lang(self, value: str | None):
        previous = os.environ.get("AI_BOARD_LANG")
        if value is None:
            os.environ.pop("AI_BOARD_LANG", None)
        else:
            os.environ["AI_BOARD_LANG"] = value
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("AI_BOARD_LANG", None)
            else:
                os.environ["AI_BOARD_LANG"] = previous

    def assert_cli_error(self, args: list[str], expected: str = "") -> str:
        output = io.StringIO()
        with redirect_stderr(output):
            self.assertEqual(main(args), 1)
        text = output.getvalue()
        if expected:
            self.assertIn(expected, text)
        return text

    def init_git_repo(self, root: Path) -> None:
        subprocess.run(["git", "-C", str(root), "init"], capture_output=True, check=True)

    def stage_file(self, root: Path, relative_path: str, content: str = "content\n") -> None:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", relative_path], capture_output=True, check=True)

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
            self.assertFalse(config["multi_agent_enabled"])
            self.assertEqual(config["git_integration"], "suggest")
            self.assertEqual(config["scope_gate"], "suggest")
            self.assertEqual(config["doctor_broad_scopes"], [".", "src", "docs", "tests"])
            self.assertIn("tests/test_cli.py", config["shared_verification_scopes"])
            self.assertEqual(config["shared_scope_warning_minutes"], 30)
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

    def test_config_command_get_set_list_and_render(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init", "--project-name", "Demo"]), 0)

            list_output = io.StringIO()
            with redirect_stdout(list_output):
                self.assertEqual(main(["--root", str(root), "config", "list"]), 0)
            self.assertIn("language: zh-CN", list_output.getvalue())
            self.assertIn("multi_agent_enabled: false", list_output.getvalue())
            self.assertIn("git_integration: suggest", list_output.getvalue())
            self.assertIn("default_lease_minutes: 240", list_output.getvalue())

            self.assertEqual(main(["--root", str(root), "add", "Config rendered task"]), 0)
            self.assertEqual(main(["--root", str(root), "config", "set", "language", "en-US"]), 0)
            board_text = (root / "docs" / "计划看板.md").read_text(encoding="utf-8")
            self.assertIn("# Planning Board", board_text)

            get_output = io.StringIO()
            with redirect_stdout(get_output):
                self.assertEqual(main(["--root", str(root), "config", "get", "language"]), 0)
            self.assertIn("language: en-US", get_output.getvalue())

            self.assertEqual(main(["--root", str(root), "config", "set", "default_lease_minutes", "5"]), 0)
            self.assertEqual(load_config(root)["default_lease_minutes"], 5)

            self.assertEqual(main(["--root", str(root), "config", "set", "doctor_broad_scopes", ".,src/app"]), 0)
            self.assertEqual(load_config(root)["doctor_broad_scopes"], [".", "src/app"])
            self.assertTrue(any(event["action"] == "config.set" and event["data"]["key"] == "doctor_broad_scopes" for event in read_events(root)))

            self.assertEqual(main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"]), 0)
            self.assertTrue(load_config(root)["multi_agent_enabled"])
            self.assertEqual(main(["--root", str(root), "config", "set", "multi_agent_enabled", "off"]), 0)
            self.assertFalse(load_config(root)["multi_agent_enabled"])

            self.assertEqual(main(["--root", str(root), "config", "set", "git_integration", "required"]), 0)
            self.assertEqual(load_config(root)["git_integration"], "required")
            self.assertEqual(main(["--root", str(root), "config", "set", "git_integration", "OFF"]), 0)
            self.assertEqual(load_config(root)["git_integration"], "off")
            self.assertEqual(main(["--root", str(root), "config", "set", "scope_gate", "required"]), 0)
            self.assertEqual(load_config(root)["scope_gate"], "required")
            self.assertEqual(main(["--root", str(root), "config", "set", "scope_gate", "OFF"]), 0)
            self.assertEqual(load_config(root)["scope_gate"], "off")

    def test_config_command_rejects_unknown_or_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init", "--project-name", "Demo"]), 0)

            self.assertIn("Unknown config key", self.assert_cli_error(["--root", str(root), "config", "get", "missing"]))
            self.assertIn("Unknown config key", self.assert_cli_error(["--root", str(root), "config", "set", "missing", "value"]))
            self.assertIn("must be a number", self.assert_cli_error(["--root", str(root), "config", "set", "default_lease_minutes", "soon"]))
            self.assertIn("must be true or false", self.assert_cli_error(["--root", str(root), "config", "set", "multi_agent_enabled", "maybe"]))
            self.assertIn(
                "git_integration must be suggest, required, or off",
                self.assert_cli_error(["--root", str(root), "config", "set", "git_integration", "always"]),
            )
            self.assertIn(
                "scope_gate must be suggest, required, or off",
                self.assert_cli_error(["--root", str(root), "config", "set", "scope_gate", "always"]),
            )
            self.assertIn("language must be zh-CN or en-US", self.assert_cli_error(["--root", str(root), "config", "set", "language", "fr-FR"]))
            self.assertEqual(load_config(root)["language"], "zh-CN")

    @unittest.skipIf(shutil.which("git") is None, "git is not available")
    def test_gate_pre_commit_returns_by_scope_gate_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.init_git_repo(root)
            self.assertEqual(main(["--root", str(root), "init", "--project-name", "Gate Demo"]), 0)
            self.assertEqual(main(["--root", str(root), "config", "set", "scope_gate", "required"]), 0)
            self.stage_file(root, "src/app.py")

            required_output = io.StringIO()
            with redirect_stdout(required_output):
                self.assertEqual(main(["--root", str(root), "gate", "pre-commit"]), 1)
            self.assertIn("issue: staged paths outside active task scope", required_output.getvalue())
            self.assertIn("src/app.py", required_output.getvalue())

            self.assertEqual(main(["--root", str(root), "config", "set", "scope_gate", "suggest"]), 0)
            suggest_output = io.StringIO()
            with redirect_stdout(suggest_output):
                self.assertEqual(main(["--root", str(root), "gate", "pre-commit"]), 0)
            self.assertIn("warning: staged paths outside active task scope", suggest_output.getvalue())

            self.assertEqual(main(["--root", str(root), "config", "set", "scope_gate", "off"]), 0)
            off_output = io.StringIO()
            with redirect_stdout(off_output):
                self.assertEqual(main(["--root", str(root), "gate", "pre-commit"]), 0)
            self.assertIn("scope gate: off", off_output.getvalue())

    @unittest.skipIf(shutil.which("git") is None, "git is not available")
    def test_hooks_install_status_uninstall_and_foreign_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.init_git_repo(root)
            self.assertEqual(main(["--root", str(root), "init", "--project-name", "Hook Demo"]), 0)

            missing_output = io.StringIO()
            with redirect_stdout(missing_output):
                self.assertEqual(main(["--root", str(root), "hooks", "status"]), 0)
            self.assertIn("pre-commit hook: missing", missing_output.getvalue())

            install_output = io.StringIO()
            with redirect_stdout(install_output):
                self.assertEqual(main(["--root", str(root), "hooks", "install", "pre-commit"]), 0)
            self.assertIn("pre-commit hook: managed", install_output.getvalue())

            uninstall_output = io.StringIO()
            with redirect_stdout(uninstall_output):
                self.assertEqual(main(["--root", str(root), "hooks", "uninstall", "pre-commit"]), 0)
            self.assertIn("pre-commit hook: missing", uninstall_output.getvalue())

            hook_path = root / ".git" / "hooks" / "pre-commit"
            hook_path.write_text("#!/bin/sh\necho foreign\n", encoding="utf-8")
            foreign_output = io.StringIO()
            with redirect_stdout(foreign_output):
                self.assertEqual(main(["--root", str(root), "hooks", "install", "pre-commit"]), 0)
            self.assertIn("pre-commit hook: foreign", foreign_output.getvalue())
            self.assertIn("did not overwrite", foreign_output.getvalue())
            self.assertEqual(hook_path.read_text(encoding="utf-8"), "#!/bin/sh\necho foreign\n")

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
            self.assertIn("STOP: 项目方向尚未与用户确认", text)
            self.assertIn("不要仅根据目录名、文件名或少量 evidence 推断项目目标", text)
            self.assertIn("确认前不要排实现任务", text)
            self.assertIn("不要直接开始编码", text)

            direction_text = (root / "docs" / "项目方向.md").read_text(encoding="utf-8")
            self.assertIn("状态：未与用户确认", direction_text)
            self.assertIn("待确认假设", direction_text)
            self.assertIn("目录名、文件名或少量代码", direction_text)

    def test_onboard_classifies_lightweight_and_existing_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "notes.md").write_text("idea", encoding="utf-8")
            (root / "snippet.py").write_text("print('hello')\n", encoding="utf-8")

            lightweight_output = io.StringIO()
            with redirect_stdout(lightweight_output):
                self.assertEqual(main(["--root", str(root), "onboard", "--init-if-missing"]), 0)
            lightweight_text = lightweight_output.getvalue()
            self.assertIn("project_kind: lightweight", lightweight_text)
            self.assertIn("STOP: 项目方向尚未与用户确认", lightweight_text)
            self.assertIn("不要仅根据目录名、文件名或少量 evidence 推断项目目标", lightweight_text)
            self.assertIn("确认前不要排实现任务", lightweight_text)

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

    def test_onboard_recommends_git_without_initializing_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "onboard", "--init-if-missing", "--project-name", "Git Demo"]), 0)
            text = output.getvalue()
            self.assertIn("Git is not initialized for this project", text)
            self.assertIn("ai-board will not do this silently", text)
            self.assertFalse((root / ".git").exists())

    def test_scan_project_files_prunes_ignored_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            seen_dirnames: list[list[str]] = []

            def fake_walk(path: Path):
                dirnames = [".git", "build", "node_modules", "src"]
                seen_dirnames.append(dirnames)
                yield str(path), dirnames, ["README.md"]

            previous_walk = onboarding.os.walk
            onboarding.os.walk = fake_walk
            try:
                files = onboarding.scan_project_files(root)
            finally:
                onboarding.os.walk = previous_walk

            self.assertEqual(files, ["README.md"])
            self.assertEqual(seen_dirnames[0], ["src"])

    def test_onboard_warns_new_agent_about_other_active_scope_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Build API"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/api.py"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "onboard", "--init-if-missing"]), 0)
            text = output.getvalue()
            self.assertIn("Active task scope locks:", text)
            self.assertIn("T-0001 owner=codex-00 lock=active", text)
            self.assertIn("scope=src/api.py", text)
            self.assertIn("if you are not codex-00, do not edit this scope", text)

    def test_onboard_hides_multi_agent_lock_notice_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Solo Demo"])
            main(["--root", str(root), "add", "Build API"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "solo", "--scope", "src/api.py"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "onboard", "--init-if-missing"]), 0)
            text = output.getvalue()
            self.assertNotIn("Active task scope locks:", text)
            self.assertNotIn("do not edit this scope", text)

    def test_onboard_lock_notice_can_use_chinese_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, self.cli_lang("zh-CN"):
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Build API"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/api.py"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "onboard", "--init-if-missing"]), 0)
            text = output.getvalue()
            self.assertIn("当前 active task scope 锁：", text)
            self.assertIn("T-0001 负责人=codex-00 锁=有效", text)
            self.assertIn("范围=src/api.py", text)
            self.assertIn("如果你不是 codex-00，不要修改这些 scope", text)

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

    def test_write_commands_refresh_generated_board_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current_doc = root / "docs" / "计划看板.md"
            archive_doc = root / "docs" / "归档计划看板.md"

            self.assertEqual(main(["--root", str(root), "init", "--project-name", "Demo"]), 0)
            self.assertIn("## 当前目标", current_doc.read_text(encoding="utf-8"))

            current_doc.write_text("stale after init", encoding="utf-8")
            self.assertEqual(main(["--root", str(root), "goal", "Ship refreshed docs"]), 0)
            self.assertIn("Ship refreshed docs", current_doc.read_text(encoding="utf-8"))

            current_doc.write_text("stale after goal", encoding="utf-8")
            self.assertEqual(main(["--root", str(root), "add", "Refresh board docs", "--priority", "P1"]), 0)
            self.assertIn("Refresh board docs", current_doc.read_text(encoding="utf-8"))

            current_doc.write_text("stale after add", encoding="utf-8")
            self.assertEqual(main(["--root", str(root), "schedule", "T-0001"]), 0)
            self.assertIn("## 下一批", current_doc.read_text(encoding="utf-8"))
            self.assertIn("Refresh board docs", current_doc.read_text(encoding="utf-8"))

            current_doc.write_text("stale after schedule", encoding="utf-8")
            self.assertEqual(main(["--root", str(root), "agents", "claim", "--kind", "codex"]), 0)
            self.assertIn("Refresh board docs", current_doc.read_text(encoding="utf-8"))

            current_doc.write_text("stale after agent claim", encoding="utf-8")
            self.assertEqual(main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "README.md"]), 0)
            self.assertIn("## 正在进行", current_doc.read_text(encoding="utf-8"))
            self.assertIn("README.md", current_doc.read_text(encoding="utf-8"))

            current_doc.write_text("stale after start", encoding="utf-8")
            self.assertEqual(main(["--root", str(root), "complete", "T-0001", "--verification", "checked", "--leftovers", "无"]), 0)
            self.assertIn("## 已完成待归档", current_doc.read_text(encoding="utf-8"))
            self.assertIn("Refresh board docs", current_doc.read_text(encoding="utf-8"))

            current_doc.write_text("stale after complete", encoding="utf-8")
            archive_doc.write_text("stale archive", encoding="utf-8")
            self.assertEqual(main(["--root", str(root), "archive", "T-0001"]), 0)
            self.assertIn("暂无", current_doc.read_text(encoding="utf-8"))
            self.assertIn("checked", archive_doc.read_text(encoding="utf-8"))

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

    def test_reopen_done_and_archived_tasks_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Reopen Demo"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Done task", "--acceptance", "checked"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "README.md"])
            main(["--root", str(root), "complete", "T-0001", "--verification", "checked"])

            self.assertEqual(main(["--root", str(root), "reopen", "T-0001", "--reason", "verification found a regression"]), 0)
            board = load_board(root)
            self.assertEqual(board["tasks"][0]["status"], "scheduled")
            self.assertEqual(board["tasks"][0]["reopen_reason"], "verification found a regression")
            self.assertIn("Done task", (root / "docs" / "计划看板.md").read_text(encoding="utf-8"))

            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "README.md"])
            main(["--root", str(root), "complete", "T-0001", "--verification", "checked again"])
            main(["--root", str(root), "archive", "T-0001"])

            self.assertEqual(main(["--root", str(root), "reopen", "T-0001", "--reason", "missed edge case"]), 0)
            board = load_board(root)
            self.assertEqual(len(board["archive"]), 0)
            self.assertEqual(board["tasks"][0]["status"], "scheduled")
            self.assertEqual(board["tasks"][0]["reopen_reason"], "missed edge case")

            history_output = io.StringIO()
            with redirect_stdout(history_output):
                self.assertEqual(main(["--root", str(root), "history", "T-0001"]), 0)
            self.assertIn("task.reopen", history_output.getvalue())

            self.assert_cli_error(["--root", str(root), "reopen", "T-0001", "--reason", "still not ready"], "Cannot reopen")

    def test_e2e_multi_agent_collaboration_conflict_release_and_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
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

    def test_next_suggests_candidates_and_warns_about_active_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Build API", "--priority", "P0"])
            main(["--root", str(root), "add", "Write docs", "--priority", "P1"])
            main(["--root", str(root), "add", "Review plan", "--priority", "P1"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/api.py"])
            board = load_board(root)
            board["tasks"][1]["scope"] = ["docs/guide.md"]
            save_board(root, board)
            main(["--root", str(root), "render"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "next"]), 0)
            text = output.getvalue()
            self.assertIn("Current active locks:", text)
            self.assertIn("T-0001 owner=codex-00", text)
            self.assertIn("do not operate this task or edit its scope", text)
            self.assertIn("T-0002 [scheduled] P1 Write docs - available: appears non-overlapping", text)
            self.assertIn("T-0003 [inbox] P1 Review plan - needs-scope: needs scope before conflict check", text)
            self.assertIn("Next action advice:", text)
            self.assertIn("Start an available non-overlapping scheduled task before waiting.", text)
            self.assertIn("declare a narrow scope first", text)

    def test_next_gives_action_advice_when_active_lock_blocks_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Core change", "--priority", "P0"])
            main(["--root", str(root), "add", "Followup core fix", "--priority", "P1"])
            main(["--root", str(root), "add", "Docs evaluation", "--priority", "P1"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "schedule", "T-0003"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/ai_board/cli.py"])
            board = load_board(root)
            board["tasks"][1]["scope"] = ["src/ai_board/cli.py"]
            board["tasks"][2]["scope"] = ["docs/项目路线/review.md"]
            save_board(root, board)
            main(["--root", str(root), "render"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "next"]), 0)
            text = output.getvalue()
            self.assertIn("T-0002 [scheduled] P1 Followup core fix - blocked-by-active-lock: overlaps active lock", text)
            self.assertIn("T-0003 [scheduled] P1 Docs evaluation - available: appears non-overlapping", text)
            self.assertIn("coordinate with the owner or split out read-only evaluation/docs work", text)
            self.assertIn("Pause only after checking for safe non-overlapping work", text)

    def test_next_warns_when_verify_scope_overlaps_active_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Change CLI", "--priority", "P0"])
            main(["--root", str(root), "add", "Version check", "--priority", "P1", "--verify-scope", "tests/test_cli.py"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "tests/test_cli.py"])
            board = load_board(root)
            board["tasks"][1]["scope"] = ["src/ai_board/__init__.py"]
            save_board(root, board)
            main(["--root", str(root), "render"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "next"]), 0)
            text = output.getvalue()
            self.assertIn("T-0002 [scheduled] P1 Version check - verification-waiting: appears non-overlapping", text)
            self.assertIn("verify scope waits on active lock", text)
            self.assertIn("T-0001 tests/test_cli.py <-> tests/test_cli.py", text)

    def test_next_surfaces_git_precoding_check_without_initializing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Git Next Demo"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "next"]), 0)
            text = output.getvalue()
            self.assertIn("Project readiness:", text)
            self.assertIn("git: recommended before coding", text)
            self.assertIn("add .gitignore, and make an initial commit", text)
            self.assertIn("ai-board will not do this silently", text)
            self.assertFalse((root / ".git").exists())

    def test_next_and_doctor_review_blocked_tasks_without_age_based_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Blocked Demo"])
            main(["--root", str(root), "add", "Still important blocked work"])
            main(["--root", str(root), "block", "T-0001"])

            next_output = io.StringIO()
            with redirect_stdout(next_output):
                self.assertEqual(main(["--root", str(root), "next"]), 0)
            next_text = next_output.getvalue()
            self.assertIn("Blocked task review:", next_text)
            self.assertIn("Do not archive by age alone", next_text)
            self.assertIn("current project direction", next_text)
            self.assertIn("ai-board reopen T-0001 --reason TEXT", next_text)

            doctor_output = io.StringIO()
            with redirect_stdout(doctor_output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 0)
            doctor_text = doctor_output.getvalue()
            self.assertIn("Blocked task review:", doctor_text)
            self.assertIn("archive only after confirming it is no longer needed", doctor_text)
            self.assertIn("doctor: ok", doctor_text)

    def test_next_prioritizes_tasks_waiting_for_full_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "add", "Needs full test"])
            main(["--root", str(root), "add", "Fresh task"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/a.py"])
            main(["--root", str(root), "complete", "T-0001", "--verification", "local passed", "--deferred-verification", "full test waits for T-9999"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "next"]), 0)
            text = output.getvalue()
            self.assertLess(text.index("Waiting for full verification:"), text.index("Candidate next work:"))
            self.assertIn("T-0001 [done] Needs full test - full test waits for T-9999", text)

    def test_agent_notices_support_inbox_ack_resolve_and_next_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Locked task"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "tests/test_cli.py"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(["--root", str(root), "tell", "--from", "codex-00", "--to", "codex-01", "--type", "wait", "--task", "T-0001", "waiting for tests"]), 0
                )
            self.assertIn("M-0001", output.getvalue())

            other_output = io.StringIO()
            with redirect_stdout(other_output):
                self.assertEqual(main(["--root", str(root), "inbox", "--agent", "codex-02"]), 0)
            self.assertIn("no notices", other_output.getvalue())

            inbox_output = io.StringIO()
            with redirect_stdout(inbox_output):
                self.assertEqual(main(["--root", str(root), "inbox", "--agent", "codex-01"]), 0)
            self.assertIn("[wait] new", inbox_output.getvalue())

            next_output = io.StringIO()
            with redirect_stdout(next_output):
                self.assertEqual(main(["--root", str(root), "next", "--agent", "codex-01"]), 0)
            text = next_output.getvalue()
            self.assertIn("Notices for codex-01:", text)
            self.assertIn("waiting for tests", text)

            ack_output = io.StringIO()
            with redirect_stdout(ack_output):
                self.assertEqual(main(["--root", str(root), "inbox", "--agent", "codex-01", "--ack", "M-0001"]), 0)
            self.assertIn("[wait] acknowledged", ack_output.getvalue())

            resolve_output = io.StringIO()
            with redirect_stdout(resolve_output):
                self.assertEqual(main(["--root", str(root), "inbox", "--agent", "codex-01", "--resolve", "M-0001"]), 0)
            self.assertIn("[wait] resolved", resolve_output.getvalue())

            empty_output = io.StringIO()
            with redirect_stdout(empty_output):
                self.assertEqual(main(["--root", str(root), "inbox", "--agent", "codex-01"]), 0)
            self.assertIn("no notices", empty_output.getvalue())

            all_output = io.StringIO()
            with redirect_stdout(all_output):
                self.assertEqual(main(["--root", str(root), "tell", "--from", "codex-00", "--to", "all", "--type", "release", "tests released soon"]), 0)
            self.assertIn("M-0002", all_output.getvalue())
            broadcast_output = io.StringIO()
            with redirect_stdout(broadcast_output):
                self.assertEqual(main(["--root", str(root), "inbox", "--agent", "codex-99"]), 0)
            self.assertIn("tests released soon", broadcast_output.getvalue())

            locks_output = io.StringIO()
            with redirect_stdout(locks_output):
                self.assertEqual(main(["--root", str(root), "locks"]), 0)
            self.assertIn("T-0001 codex-00 lock=active", locks_output.getvalue())

    def test_multi_agent_disabled_hides_notice_prompts_and_scope_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Solo Demo"])
            main(["--root", str(root), "add", "Task A", "--acceptance", "checked"])
            main(["--root", str(root), "add", "Task B", "--acceptance", "checked"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "solo", "--scope", "src/app.py"])
            main(["--root", str(root), "tell", "--from", "other", "--to", "solo", "--type", "request", "--task", "T-0001", "please confirm"])

            next_output = io.StringIO()
            with redirect_stdout(next_output):
                self.assertEqual(main(["--root", str(root), "next", "--agent", "solo"]), 0)
            next_text = next_output.getvalue()
            self.assertNotIn("Notices for solo:", next_text)
            self.assertNotIn("Next action advice:", next_text)

            self.assertEqual(main(["--root", str(root), "start", "T-0002", "--agent", "solo-2", "--scope", "src/app.py"]), 0)
            doctor_output = io.StringIO()
            with redirect_stdout(doctor_output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 0)
            self.assertIn("scope conflicts: ok", doctor_output.getvalue())

    def test_multi_agent_enabled_restores_notice_prompts_and_scope_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "add", "Task A", "--acceptance", "checked"])
            main(["--root", str(root), "add", "Task B", "--acceptance", "checked"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/app.py"])
            main(["--root", str(root), "tell", "--from", "codex-01", "--to", "codex-00", "--type", "request", "--task", "T-0001", "please confirm"])

            next_output = io.StringIO()
            with redirect_stdout(next_output):
                self.assertEqual(main(["--root", str(root), "next", "--agent", "codex-00"]), 0)
            next_text = next_output.getvalue()
            self.assertIn("Notices for codex-00:", next_text)
            self.assertIn("Next action advice:", next_text)

            self.assert_cli_error(["--root", str(root), "start", "T-0002", "--agent", "codex-01", "--scope", "src/app.py"], "Scope is locked")

    def test_inbox_can_fail_when_unresolved_notices_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "tell", "--from", "codex-00", "--to", "codex-01", "--type", "request", "please confirm"])

            unresolved_output = io.StringIO()
            with redirect_stdout(unresolved_output):
                self.assertEqual(main(["--root", str(root), "inbox", "--agent", "codex-01", "--fail-on-unresolved"]), 1)
            unresolved_text = unresolved_output.getvalue()
            self.assertIn("M-0001", unresolved_text)
            self.assertIn("unresolved notices: 1", unresolved_text)

            resolve_output = io.StringIO()
            with redirect_stdout(resolve_output):
                self.assertEqual(main(["--root", str(root), "inbox", "--agent", "codex-01", "--resolve", "M-0001"]), 0)
            self.assertIn("[request] resolved", resolve_output.getvalue())

            clear_output = io.StringIO()
            with redirect_stdout(clear_output):
                self.assertEqual(main(["--root", str(root), "inbox", "--agent", "codex-01", "--fail-on-unresolved"]), 0)
            self.assertIn("no notices", clear_output.getvalue())

    def test_complete_and_archive_warn_about_unresolved_owner_notices(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Notice task"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/a.py"])
            main(["--root", str(root), "tell", "--from", "codex-01", "--to", "codex-00", "--type", "request", "--task", "T-0001", "please confirm handoff"])

            complete_output = io.StringIO()
            with redirect_stdout(complete_output):
                self.assertEqual(main(["--root", str(root), "complete", "T-0001", "--verification", "checked"]), 0)
            complete_text = complete_output.getvalue()
            self.assertIn("T-0001 [done] P2 Notice task", complete_text)
            self.assertIn("warning: codex-00 still has unresolved notices", complete_text)
            self.assertIn("M-0001", complete_text)

            archive_output = io.StringIO()
            with redirect_stdout(archive_output):
                self.assertEqual(main(["--root", str(root), "archive", "T-0001"]), 0)
            archive_text = archive_output.getvalue()
            self.assertIn("T-0001 [archived] P2 Notice task", archive_text)
            self.assertIn("warning: codex-00 still has unresolved notices", archive_text)
            self.assertIn("M-0001", archive_text)

            inbox_output = io.StringIO()
            with redirect_stdout(inbox_output):
                self.assertEqual(main(["--root", str(root), "inbox", "--agent", "codex-00"]), 0)
            self.assertIn("[request] new", inbox_output.getvalue())

    def test_verify_scope_and_deferred_verification_are_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "add", "Version check", "--verify-scope", "tests/test_version.py", "pyproject.toml"])
            board = load_board(root)
            self.assertEqual(board["tasks"][0]["verify_scope"], ["pyproject.toml", "tests/test_version.py"])

            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/ai_board/__init__.py"])
            main(
                [
                    "--root",
                    str(root),
                    "complete",
                    "T-0001",
                    "--verification",
                    "version test passed",
                    "--deferred-verification",
                    "full test waits for T-0002",
                    "--leftovers",
                    "无",
                ]
            )

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "show", "T-0001"]), 0)
            text = output.getvalue()
            self.assertIn("verify_scope: pyproject.toml, tests/test_version.py", text)
            self.assertIn("deferred_verification: full test waits for T-0002", text)

    def test_next_reports_stale_generated_board_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "add", "Write docs"])
            (root / "docs" / "计划看板.md").write_text("stale", encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "next"]), 0)
            text = output.getvalue()
            self.assertIn("Generated board warning:", text)
            self.assertIn("generated doc stale", text)
            self.assertIn("trust JSON and run ai-board render", text)

    def test_schedule_and_start_active_task_errors_include_owner_scope_and_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/a.py"])

            schedule_error = self.assert_cli_error(["--root", str(root), "schedule", "T-0001"], "already active")
            self.assertIn("owner=codex-00", schedule_error)
            self.assertIn("scope=src/a.py", schedule_error)
            self.assertIn("lease_expires_at=", schedule_error)

            start_error = self.assert_cli_error(["--root", str(root), "start", "T-0001", "--agent", "codex-01", "--scope", "src/b.py"], "already active")
            self.assertIn("owner=codex-00", start_error)
            self.assertIn("scope=src/a.py", start_error)
            self.assertIn("lease_expires_at=", start_error)

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

    def test_blocked_tasks_can_be_archived_or_reopened_without_hand_editing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Stale blocked task"])
            main(["--root", str(root), "add", "Retry blocked task"])
            main(["--root", str(root), "block", "T-0001"])
            main(["--root", str(root), "block", "T-0002"])

            self.assertEqual(main(["--root", str(root), "archive", "T-0001"]), 0)
            board = load_board(root)
            self.assertFalse(any(task["id"] == "T-0001" for task in board["tasks"]))
            archived = next(task for task in board["archive"] if task["id"] == "T-0001")
            self.assertEqual(archived["status"], "archived")

            self.assertEqual(main(["--root", str(root), "reopen", "T-0002", "--reason", "Blocker resolved"]), 0)
            reopened = find_task(load_board(root), "T-0002")
            self.assertEqual(reopened["status"], "scheduled")
            self.assertEqual(reopened["reopen_reason"], "Blocker resolved")
            self.assert_cli_error(["--root", str(root), "complete", "T-0002", "--verification", "checked"], "from scheduled to done")

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
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
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

    def test_root_scope_overlaps_every_project_path(self) -> None:
        self.assertTrue(scopes_overlap(".", "src"))
        self.assertTrue(scopes_overlap("src", "."))
        self.assertTrue(scopes_overlap(".", "README.md"))
        self.assertTrue(scopes_overlap(".", "."))
        self.assertFalse(scopes_overlap("src/api", "src/apix"))

    def test_root_scope_variants_are_normalized_before_conflict_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "./", ".//"])

            board = load_board(root)
            self.assertEqual(find_task(board, "T-0001")["scope"], ["."])
            self.assert_cli_error(["--root", str(root), "start", "T-0002", "--agent", "b", "--scope", "README.md"], "Scope is locked")

    def test_root_scope_blocks_subpath_start_and_reports_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "."])

            self.assert_cli_error(["--root", str(root), "start", "T-0002", "--agent", "b", "--scope", "src"], "Scope is locked")
            main(["--root", str(root), "start", "T-0002", "--agent", "b", "--scope", "src", "--force"])

            conflicts_output = io.StringIO()
            with redirect_stdout(conflicts_output):
                self.assertEqual(main(["--root", str(root), "conflicts", "--fail-on-conflict"]), 1)
            self.assertIn(". <-> src", conflicts_output.getvalue())

    def test_next_treats_root_scope_as_blocking_subpath_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "add", "Whole repo", "--priority", "P0"])
            main(["--root", str(root), "add", "Source change", "--priority", "P1"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "."])
            board = load_board(root)
            board["tasks"][1]["scope"] = ["src"]
            save_board(root, board)

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "next"]), 0)
            self.assertIn("T-0002 [scheduled] P1 Source change - blocked-by-active-lock", output.getvalue())

    def test_next_warns_when_root_lock_blocks_verify_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init", "--project-name", "Team Demo"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "add", "Whole repo", "--priority", "P0"])
            main(["--root", str(root), "add", "Verify source", "--priority", "P1", "--verify-scope", "src"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "."])
            board = load_board(root)
            board["tasks"][1]["scope"] = ["README.md"]
            save_board(root, board)

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "next"]), 0)
            text = output.getvalue()
            self.assertIn("T-0002 [scheduled] P1 Verify source - blocked-by-active-lock", text)
            self.assertIn("T-0001 . <-> src", text)

    def test_force_overlap_is_reported_by_conflicts_and_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "add", "Task A", "--acceptance", "checked"])
            main(["--root", str(root), "add", "Task B", "--acceptance", "checked"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "."])
            main(["--root", str(root), "start", "T-0002", "--agent", "b", "--scope", "src", "--force"])

            conflicts_output = io.StringIO()
            with redirect_stdout(conflicts_output):
                self.assertEqual(main(["--root", str(root), "conflicts", "--fail-on-conflict"]), 1)
            self.assertIn("on . <-> src", conflicts_output.getvalue())

            doctor_output = io.StringIO()
            with redirect_stdout(doctor_output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            self.assertIn("scope conflict: T-0001 and T-0002 overlap on . <-> src", doctor_output.getvalue())

    def test_conflicts_can_reveal_solo_mode_overlap_without_blocking_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "solo-a", "--scope", "."])
            self.assertEqual(main(["--root", str(root), "start", "T-0002", "--agent", "solo-b", "--scope", "src"]), 0)

            conflicts_output = io.StringIO()
            with redirect_stdout(conflicts_output):
                self.assertEqual(main(["--root", str(root), "conflicts", "--fail-on-conflict"]), 1)
            self.assertIn("T-0001 (solo-a) conflicts with T-0002 (solo-b) on . <-> src", conflicts_output.getvalue())

    def test_rescope_to_root_is_blocked_by_existing_subpath_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "docs"])
            main(["--root", str(root), "start", "T-0002", "--agent", "b", "--scope", "src/app.py"])

            self.assert_cli_error(["--root", str(root), "rescope", "T-0001", "--agent", "a", "--scope", "."], "Scope is locked")

    def test_expired_root_lock_does_not_block_subpath_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", ".", "--lease-minutes", "1"])
            board = load_board(root)
            find_task(board, "T-0001")["lease_expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(microsecond=0).isoformat()
            save_board(root, board)

            self.assertEqual(main(["--root", str(root), "start", "T-0002", "--agent", "b", "--scope", "src"]), 0)
            self.assertEqual(main(["--root", str(root), "conflicts", "--fail-on-conflict"]), 0)

    def test_start_rejects_empty_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "schedule", "T-0001"])

            self.assert_cli_error(["--root", str(root), "start", "T-0001", "--agent", "codex-00"], "Task scope is required")

            board = load_board(root)
            task = board["tasks"][0]
            self.assertEqual(task["status"], "scheduled")
            self.assertEqual(task["scope"], [])
            self.assertEqual(board["agents"][0]["status"], "busy")
            self.assertEqual(board["agents"][0]["task_id"], "")

    def test_scope_paths_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "schedule", "T-0001"])

            self.assertEqual(main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", r"src\..\docs", "./docs//"]), 0)

            board = load_board(root)
            self.assertEqual(board["tasks"][0]["scope"], ["docs"])

    def test_start_rejects_scope_argument_that_looks_like_merged_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "schedule", "T-0001"])

            error = self.assert_cli_error(
                ["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "src/a.py tests/test_cli.py"],
                "Scope path contains spaces",
            )
            self.assertIn("pass each path as a separate --scope argument", error)

    def test_start_allows_existing_scope_path_with_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path_with_spaces = root / "docs" / "My Guide.md"
            path_with_spaces.parent.mkdir(parents=True)
            path_with_spaces.write_text("# Guide\n", encoding="utf-8")
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "schedule", "T-0001"])

            self.assertEqual(main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "docs/My Guide.md"]), 0)

            board = load_board(root)
            self.assertEqual(board["tasks"][0]["scope"], ["docs/My Guide.md"])

    def test_normalized_scope_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
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
            self.assertEqual(board["tasks"][0]["scope"], ["src"])
            self.assertEqual(board["tasks"][0]["lock_owner"], "")
            self.assertEqual(board["tasks"][0]["lease_expires_at"], "")
            events = self.read_events(root)
            self.assertIn("task.renew", [event["action"] for event in events])
            self.assertIn("task.unlock", [event["action"] for event in events])

    def test_unlock_preserves_scope_and_rescope_reacquires_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "docs"])
            self.assertEqual(main(["--root", str(root), "unlock", "T-0001", "--agent", "a"]), 0)
            self.assertEqual(main(["--root", str(root), "agents", "release", "a", "--force"]), 0)

            board = load_board(root)
            self.assertEqual(board["tasks"][0]["scope"], ["docs"])
            self.assertEqual(board["tasks"][0]["lock_owner"], "")

            self.assertEqual(main(["--root", str(root), "start", "T-0002", "--agent", "b", "--scope", "docs/guide.md"]), 0)
            self.assertEqual(
                main(
                    [
                        "--root",
                        str(root),
                        "rescope",
                        "T-0001",
                        "--agent",
                        "a",
                        "--scope",
                        "src/app.py",
                        "--verify-scope",
                        "tests/test_app.py",
                    ]
                ),
                0,
            )

            board = load_board(root)
            task = find_task(board, "T-0001")
            self.assertEqual(task["scope"], ["src/app.py"])
            self.assertEqual(task["verify_scope"], ["tests/test_app.py"])
            self.assertEqual(task["lock_owner"], "a")
            self.assertEqual(main(["--root", str(root), "conflicts", "--fail-on-conflict"]), 0)

            self.assert_cli_error(["--root", str(root), "rescope", "T-0001", "--agent", "a", "--scope", "docs/guide.md"], "Scope is locked")
            events = self.read_events(root)
            self.assertIn("task.rescope", [event["action"] for event in events])

    def test_doctor_no_scope_issue_suggests_rescope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "a", "--scope", "src/a.py"])
            board = load_board(root)
            task = find_task(board, "T-0001")
            task["scope"] = []
            save_board(root, board)

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            self.assertIn("ai-board rescope T-0001 --agent a --scope <paths...>", output.getvalue())

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

    def test_verification_evidence_records_board_data_and_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Verified task"])

            passed = record_verification_evidence(
                root,
                "T-0001",
                kind="automated",
                status="passed",
                agent="codex",
                command="uv run python -m unittest",
                exit_code=0,
                summary="tests ok",
                output_excerpt="OK",
                scope=["tests", "src\\ai_board"],
            )
            failed = record_verification_evidence(root, "T-0001", kind="automated", status="failed", exit_code=1, summary="tests failed")
            deferred = record_verification_evidence(root, "T-0001", kind="deferred", status="deferred", summary="waiting for staging")

            self.assertEqual(passed["id"], "V-0001")
            self.assertEqual(failed["id"], "V-0002")
            self.assertEqual(deferred["id"], "V-0003")
            self.assertEqual(passed["scope"], ["src/ai_board", "tests"])

            board = load_board(root)
            self.assertEqual(board["next_verification_id"], 4)
            self.assertEqual([item["id"] for item in board["verifications"]], ["V-0001", "V-0002", "V-0003"])

            events = self.read_events(root)
            actions = [event["action"] for event in events]
            self.assertIn("verification.recorded", actions)
            self.assertIn("verification.failed", actions)
            self.assertIn("verification.deferred", actions)
            event_data = [event["data"] for event in events if event["action"].startswith("verification.")]
            self.assertEqual([data["verification_id"] for data in event_data], ["V-0001", "V-0002", "V-0003"])

    def test_verify_run_records_passed_automated_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Verified command"])
            command = f'"{sys.executable}" -c "print(123)"'

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "verify", "T-0001", "--agent", "codex", "--run", command, "--scope", "tests"]), 0)

            self.assertIn("V-0001 [passed] automated task=T-0001", output.getvalue())
            board = load_board(root)
            verification = board["verifications"][0]
            self.assertEqual(verification["kind"], "automated")
            self.assertEqual(verification["status"], "passed")
            self.assertEqual(verification["exit_code"], 0)
            self.assertEqual(verification["summary"], "123")
            self.assertEqual(verification["output_excerpt"], "123")
            self.assertEqual(verification["scope"], ["tests"])

    def test_verify_run_records_failed_evidence_and_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Failing command"])
            command = f'"{sys.executable}" -c "import sys; print(\'bad\'); sys.exit(3)"'

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "verify", "T-0001", "--agent", "codex", "--run", command]), 1)

            self.assertIn("V-0001 [failed] automated task=T-0001", output.getvalue())
            board = load_board(root)
            verification = board["verifications"][0]
            self.assertEqual(verification["status"], "failed")
            self.assertEqual(verification["exit_code"], 3)
            self.assertEqual(verification["summary"], "bad")
            self.assertEqual(read_events(root)[-1]["action"], "verification.failed")

    def test_verify_run_truncates_long_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Long command"])
            command = f'"{sys.executable}" -c "print(\'x\' * 5000)"'

            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--root", str(root), "verify", "T-0001", "--agent", "codex", "--run", command]), 0)

            verification = load_board(root)["verifications"][0]
            self.assertLessEqual(len(verification["summary"]), 240)
            excerpt = verification["output_excerpt"]
            self.assertLess(len(excerpt), 4100)
            self.assertIn("output truncated", excerpt)

    def test_verify_manual_records_manual_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Manual check"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "verify", "T-0001", "--agent", "codex", "--manual", "checked in browser"]), 0)

            self.assertIn("V-0001 [passed] manual task=T-0001", output.getvalue())
            verification = load_board(root)["verifications"][0]
            self.assertEqual(verification["kind"], "manual")
            self.assertEqual(verification["status"], "passed")
            self.assertEqual(verification["summary"], "checked in browser")
            self.assertEqual(verification["command"], "")
            self.assertIsNone(verification["exit_code"])

    def test_complete_can_link_passed_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Verified complete"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex", "--scope", "README.md"])
            main(["--root", str(root), "verify", "T-0001", "--agent", "codex", "--manual", "checked output"])

            self.assertEqual(main(["--root", str(root), "complete", "T-0001", "--verification-id", "V-0001", "--leftovers", "无"]), 0)
            board = load_board(root)
            task = board["tasks"][0]
            self.assertEqual(task["status"], "done")
            self.assertEqual(task["verification_ids"], ["V-0001"])
            self.assertEqual(task["verification"], "verification evidence: V-0001")

            show_output = io.StringIO()
            with redirect_stdout(show_output):
                self.assertEqual(main(["--root", str(root), "show", "T-0001"]), 0)
            show_text = show_output.getvalue()
            self.assertIn("verification evidence", show_text)
            self.assertIn("V-0001 [passed] manual: checked output", show_text)

            history_output = io.StringIO()
            with redirect_stdout(history_output):
                self.assertEqual(main(["--root", str(root), "history", "T-0001"]), 0)
            history_text = history_output.getvalue()
            self.assertIn("verification_id=V-0001", history_text)
            self.assertIn("verification_ids=V-0001", history_text)

    def test_complete_rejects_missing_or_cross_task_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "add", "Task B"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "schedule", "T-0002"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex", "--scope", "README.md"])
            main(["--root", str(root), "verify", "T-0002", "--agent", "codex", "--manual", "other task checked"])

            self.assert_cli_error(["--root", str(root), "complete", "T-0001", "--verification-id", "V-9999"], "Verification not found")
            self.assert_cli_error(["--root", str(root), "complete", "T-0001", "--verification-id", "V-0001"], "belongs to T-0002")

    def test_complete_rejects_failed_evidence_unless_forced_with_leftovers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Failed evidence"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex", "--scope", "README.md"])
            record_verification_evidence(root, "T-0001", kind="automated", status="failed", exit_code=1, summary="tests failed")

            self.assert_cli_error(["--root", str(root), "complete", "T-0001", "--verification-id", "V-0001"], "not passed")
            self.assert_cli_error(["--root", str(root), "complete", "T-0001", "--verification-id", "V-0001", "--force"], "requires --leftovers")
            self.assertEqual(
                main(["--root", str(root), "complete", "T-0001", "--verification-id", "V-0001", "--force", "--leftovers", "known failing test remains"]),
                0,
            )
            task = load_board(root)["tasks"][0]
            self.assertTrue(task["verification_force"])
            self.assertEqual(task["verification_ids"], ["V-0001"])

    def test_doctor_reports_dangling_verification_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Dangling evidence"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex", "--scope", "README.md"])
            main(["--root", str(root), "verify", "T-0001", "--agent", "codex", "--manual", "checked"])
            main(["--root", str(root), "complete", "T-0001", "--verification-id", "V-0001"])
            board = load_board(root)
            board["tasks"][0]["verification_ids"] = ["V-9999"]
            save_board(root, board)

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            self.assertIn("task T-0001 references missing verification V-9999", output.getvalue())

    def test_show_defaults_to_human_output_and_can_print_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "add", "Document API", "--lane", "文档治理", "--acceptance", "API is documented"])

            human_output = io.StringIO()
            with redirect_stdout(human_output):
                self.assertEqual(main(["--root", str(root), "show", "T-0001"]), 0)
            human_text = human_output.getvalue()
            self.assertIn("T-0001 [inbox] P2 Document API", human_text)
            self.assertIn("lane: 文档治理", human_text)
            self.assertIn("acceptance:", human_text)

            json_output = io.StringIO()
            with redirect_stdout(json_output):
                self.assertEqual(main(["--root", str(root), "show", "T-0001", "--format", "json"]), 0)
            data = json.loads(json_output.getvalue())
            self.assertEqual(data["id"], "T-0001")

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

            output = io.StringIO()
            with redirect_stderr(output):
                self.assertEqual(main(["--root", str(root), "add", "Still recorded in board"]), 0)
            self.assertIn("warning: could not append event log", output.getvalue())

            board = load_board(root)
            self.assertEqual(board["tasks"][0]["title"], "Still recorded in board")

            doctor_output = io.StringIO()
            with redirect_stdout(doctor_output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            self.assertIn("event log fallback", doctor_output.getvalue())

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

            commands = [[sys.executable, "-m", "ai_board", "--root", str(root), "add", f"Task {index}"] for index in range(6)]
            processes = [
                subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace") for command in commands
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
            self.assertEqual(board["verifications"], [])
            self.assertEqual(board["next_verification_id"], 1)
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

    def test_doctor_git_integration_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)

            suggest_output = io.StringIO()
            with redirect_stdout(suggest_output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 0)
            self.assertIn("git: recommended before coding", suggest_output.getvalue())
            self.assertIn("ai-board will not do this silently", suggest_output.getvalue())

            self.assertEqual(main(["--root", str(root), "config", "set", "git_integration", "required"]), 0)
            required_output = io.StringIO()
            with redirect_stdout(required_output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            self.assertIn("git is required but this project is not initialized", required_output.getvalue())

            self.assertEqual(main(["--root", str(root), "config", "set", "git_integration", "off"]), 0)
            off_output = io.StringIO()
            with redirect_stdout(off_output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 0)
            self.assertIn("git: skipped", off_output.getvalue())

    @unittest.skipIf(shutil.which("git") is None, "git is not available")
    def test_doctor_scope_gate_required_requires_managed_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.init_git_repo(root)
            self.assertEqual(main(["--root", str(root), "init", "--project-name", "Gate Doctor"]), 0)
            self.assertEqual(main(["--root", str(root), "config", "set", "scope_gate", "required"]), 0)

            missing_output = io.StringIO()
            with redirect_stdout(missing_output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            self.assertIn("scope_gate is required but pre-commit hook is missing", missing_output.getvalue())

            self.assertEqual(main(["--root", str(root), "hooks", "install", "pre-commit"]), 0)
            managed_output = io.StringIO()
            with redirect_stdout(managed_output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 0)
            self.assertIn("scope gate hook: managed", managed_output.getvalue())

    def test_doctor_reports_active_task_and_agent_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            board = load_board(root)
            board["tasks"].append(
                {
                    "id": "T-0001",
                    "title": "Broken active",
                    "priority": "P2",
                    "status": "active",
                    "lane": "默认",
                    "owner_agent": "codex-00",
                    "scope": ["."],
                    "depends_on": [],
                    "acceptance": [],
                    "created_at": now_iso(),
                    "updated_at": (datetime.now(timezone.utc) - timedelta(hours=72)).replace(microsecond=0).isoformat(),
                }
            )
            board["agents"].append(
                {
                    "id": "codex-00",
                    "kind": "codex",
                    "status": "busy",
                    "task_id": "T-0001",
                    "lease_expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(microsecond=0).isoformat(),
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
            save_board(root, board)

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            text = output.getvalue()
            self.assertIn("active task T-0001 scope is broad", text)
            self.assertIn("prefer specific files or smaller subdirectories", text)
            self.assertIn("active task T-0001 has no acceptance criteria", text)
            self.assertIn("active task T-0001 has not been updated", text)
            self.assertIn("agent codex-00 lease expires soon", text)

    def test_doctor_reports_default_broad_directory_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)
            board = load_board(root)
            board["tasks"].append(
                {
                    "id": "T-0001",
                    "title": "Broad source task",
                    "priority": "P2",
                    "status": "active",
                    "lane": "默认",
                    "owner_agent": "codex-00",
                    "scope": ["src"],
                    "depends_on": [],
                    "acceptance": ["checked"],
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
            board["agents"].append(
                {
                    "id": "codex-00",
                    "kind": "codex",
                    "status": "busy",
                    "task_id": "T-0001",
                    "lease_expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).replace(microsecond=0).isoformat(),
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
            save_board(root, board)
            main(["--root", str(root), "render"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            self.assertIn("active task T-0001 scope is broad (src)", output.getvalue())

    def test_doctor_reports_long_held_shared_verification_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)
            board = load_board(root)
            board["tasks"].append(
                {
                    "id": "T-0001",
                    "title": "Shared test task",
                    "priority": "P2",
                    "status": "active",
                    "lane": "默认",
                    "owner_agent": "codex-00",
                    "scope": ["tests/test_cli.py"],
                    "verify_scope": [],
                    "depends_on": [],
                    "acceptance": ["checked"],
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                    "locked_at": (datetime.now(timezone.utc) - timedelta(minutes=45)).replace(microsecond=0).isoformat(),
                    "lease_expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).replace(microsecond=0).isoformat(),
                    "lock_owner": "codex-00",
                }
            )
            board["agents"].append(
                {
                    "id": "codex-00",
                    "kind": "codex",
                    "status": "busy",
                    "task_id": "T-0001",
                    "lease_expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).replace(microsecond=0).isoformat(),
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
            save_board(root, board)
            main(["--root", str(root), "render"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            text = output.getvalue()
            self.assertIn("holds shared verification scope", text)
            self.assertIn("other tasks may be waiting for full verification", text)

    def test_doctor_reports_active_task_and_agent_integrity_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
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
                    "acceptance": ["checked"],
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
            main(["--root", str(root), "render"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            text = output.getvalue()
            self.assertIn("active task T-0001 has no scope", text)
            self.assertIn("agent codex-00 points to T-9999", text)

    def test_doctor_reports_expired_owner_agent_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)
            main(["--root", str(root), "config", "set", "multi_agent_enabled", "true"])
            board = load_board(root)
            board["tasks"].append(
                {
                    "id": "T-0001",
                    "title": "Expired owner",
                    "priority": "P2",
                    "status": "active",
                    "lane": "默认",
                    "owner_agent": "codex-00",
                    "scope": ["src/app.py"],
                    "depends_on": [],
                    "acceptance": ["checked"],
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                    "lock_owner": "codex-00",
                    "lease_expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).replace(microsecond=0).isoformat(),
                }
            )
            board["agents"].append(
                {
                    "id": "codex-00",
                    "kind": "codex",
                    "status": "busy",
                    "task_id": "T-0001",
                    "lease_expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(microsecond=0).isoformat(),
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
            save_board(root, board)
            main(["--root", str(root), "render"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 1)
            self.assertIn("agent codex-00 lease is expired", output.getvalue())

    def test_doctor_business_thresholds_can_be_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)
            config_file = root / ".ai-board" / "config.json"
            config = json.loads(config_file.read_text(encoding="utf-8"))
            config.update(
                {
                    "doctor_stale_active_hours": 100,
                    "doctor_lease_warning_minutes": 5,
                    "doctor_broad_scopes": ["."],
                }
            )
            config_file.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            board = load_board(root)
            board["tasks"].append(
                {
                    "id": "T-0001",
                    "title": "Healthy enough active",
                    "priority": "P2",
                    "status": "active",
                    "lane": "默认",
                    "owner_agent": "codex-00",
                    "scope": ["src"],
                    "depends_on": [],
                    "acceptance": ["checked"],
                    "created_at": now_iso(),
                    "updated_at": (datetime.now(timezone.utc) - timedelta(hours=72)).replace(microsecond=0).isoformat(),
                }
            )
            board["agents"].append(
                {
                    "id": "codex-00",
                    "kind": "codex",
                    "status": "busy",
                    "task_id": "T-0001",
                    "lease_expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(microsecond=0).isoformat(),
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
            save_board(root, board)
            main(["--root", str(root), "render"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 0)
            self.assertIn("doctor: ok", output.getvalue())

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
