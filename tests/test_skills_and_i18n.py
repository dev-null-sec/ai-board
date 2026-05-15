from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_board.cli import main
from ai_board.store import load_board, now_iso, save_board


class SkillsAndI18nTests(unittest.TestCase):
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

    def test_cli_human_output_can_use_chinese_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, self.cli_lang("zh-CN"):
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Document API", "--acceptance", "checked"])
            main(["--root", str(root), "schedule", "T-0001"])
            main(["--root", str(root), "start", "T-0001", "--agent", "codex-00", "--scope", "src/api.py"])

            status_output = io.StringIO()
            with redirect_stdout(status_output):
                self.assertEqual(main(["--root", str(root), "status"]), 0)
            self.assertIn("项目: ", status_output.getvalue())
            self.assertIn("active: 1", status_output.getvalue())

            show_output = io.StringIO()
            with redirect_stdout(show_output):
                self.assertEqual(main(["--root", str(root), "show", "T-0001"]), 0)
            self.assertIn("负责人: codex-00", show_output.getvalue())
            self.assertIn("验收标准:", show_output.getvalue())

            agents_output = io.StringIO()
            with redirect_stdout(agents_output):
                self.assertEqual(main(["--root", str(root), "agents", "list"]), 0)
            self.assertIn("类型=codex", agents_output.getvalue())
            self.assertIn("任务=T-0001", agents_output.getvalue())

            locks_output = io.StringIO()
            with redirect_stdout(locks_output):
                self.assertEqual(main(["--root", str(root), "locks"]), 0)
            self.assertIn("锁=active", locks_output.getvalue())
            self.assertIn("范围=src/api.py", locks_output.getvalue())

            doctor_output = io.StringIO()
            with redirect_stdout(doctor_output):
                self.assertEqual(main(["--root", str(root), "doctor", "--fail-on-issue"]), 0)
            doctor_text = doctor_output.getvalue()
            self.assertIn("board 锁：正常", doctor_text)
            self.assertIn("doctor：正常", doctor_text)

            json_output = io.StringIO()
            with redirect_stdout(json_output):
                self.assertEqual(main(["--root", str(root), "show", "T-0001", "--format", "json"]), 0)
            data = json.loads(json_output.getvalue())
            self.assertIn("owner_agent", data)
            self.assertEqual(data["status"], "active")

    def test_board_error_can_use_chinese_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, self.cli_lang("zh-CN"):
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            main(["--root", str(root), "agents", "claim", "--kind", "codex"])
            main(["--root", str(root), "add", "Task A"])
            main(["--root", str(root), "schedule", "T-0001"])

            error = self.assert_cli_error(["--root", str(root), "start", "T-0001", "--agent", "codex-00"], "任务 scope 是必需的")
            self.assertIn("--scope src/app.py README.md", error)

    def test_doctor_issue_can_use_chinese_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, self.cli_lang("zh-CN"):
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
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
            text = output.getvalue()
            self.assertIn("问题: active 任务 T-0001 的 scope 过宽", text)
            self.assertIn("具体文件或更小目录", text)

    def test_lang_command_prints_bilingual_shell_hints(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["lang", "zh-CN"]), 0)
        text = output.getvalue()
        self.assertIn("Language / 语言: zh-CN", text)
        self.assertIn('$env:AI_BOARD_LANG="zh-CN"', text)
        self.assertIn("One-shot / 单次运行:", text)

    def test_lang_command_defaults_to_chinese_hints(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["lang"]), 0)
        text = output.getvalue()
        self.assertIn("Language / 语言: zh-CN", text)
        self.assertIn("export AI_BOARD_LANG=zh-CN", text)

    def test_lang_argument_overrides_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, self.cli_lang("zh-CN"):
            root = Path(temp_dir)
            main(["--root", str(root), "init"])
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "--lang", "en-US", "status"]), 0)
            self.assertIn("project:", output.getvalue())
            self.assertNotIn("项目:", output.getvalue())

    def test_skills_commands_do_not_require_board(self) -> None:
        self.assertEqual(main(["skills"]), 0)
        self.assertEqual(main(["skills", "list"]), 0)
        core_output = io.StringIO()
        with redirect_stdout(core_output):
            self.assertEqual(main(["skills", "get", "core"]), 0)
        core_text = core_output.getvalue()
        self.assertIn("inbox --agent codex-01 --fail-on-unresolved", core_text)
        self.assertIn("If it returns non-zero, do not finish", core_text)
        self.assertIn("failed handoff", core_text)

        full_output = io.StringIO()
        with redirect_stdout(full_output):
            self.assertEqual(main(["skills", "get", "core", "--full"]), 0)
        self.assertIn("[--fail-on-unresolved]", full_output.getvalue())

    def test_key_help_output_includes_examples(self) -> None:
        for command in ("add", "start", "show", "skills"):
            output = io.StringIO()
            with redirect_stdout(output), self.assertRaises(SystemExit) as error:
                main([command, "--help"])
            self.assertEqual(error.exception.code, 0)
            self.assertIn("Examples:", output.getvalue())

    def test_start_help_guides_agents_to_use_narrow_scope(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as error:
            main(["start", "--help"])
        self.assertEqual(error.exception.code, 0)
        text = output.getvalue()
        self.assertIn("--scope is required", text)
        self.assertIn("Keep it narrow", text)
        self.assertIn("specific files or small subdirectories", text)

    def test_help_output_can_use_chinese_language(self) -> None:
        with self.cli_lang("zh-CN"):
            output = io.StringIO()
            with redirect_stdout(output), self.assertRaises(SystemExit) as error:
                main(["-h"])
            self.assertEqual(error.exception.code, 0)
            text = output.getvalue()
            self.assertIn("用法:", text)
            self.assertIn("位置参数:", text)
            self.assertIn("选项:", text)
            self.assertIn("创建项目看板。", text)
            self.assertIn("人类可读输出语言", text)

    def test_lang_argument_controls_help_language(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as error:
            main(["--lang", "zh-CN", "-h"])
        self.assertEqual(error.exception.code, 0)
        self.assertIn("读取 CLI 内置的 AI 使用指南。", output.getvalue())

    def test_argparse_errors_can_use_chinese_language(self) -> None:
        with self.cli_lang("zh-CN"):
            output = io.StringIO()
            with redirect_stderr(output), self.assertRaises(SystemExit) as error:
                main([])
            self.assertEqual(error.exception.code, 2)
            text = output.getvalue()
            self.assertIn("用法:", text)
            self.assertIn("错误:", text)
            self.assertIn("缺少必填参数:", text)

    def test_core_skill_guide_mentions_narrow_scope(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["skills", "get", "core"]), 0)
        text = output.getvalue()
        self.assertIn("honest, narrow", text)
        self.assertIn("broad roots", text)
