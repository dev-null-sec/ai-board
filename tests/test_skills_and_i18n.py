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

REPO_ROOT = Path(__file__).resolve().parents[1]


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
        self.assertIn("hard direction gate", text)
        self.assertIn("Directory names, file names, and small evidence fragments are only hypotheses", text)
        self.assertIn("Do not write final roadmap language", text)
        self.assertIn("Install the agent skill according to that agent's skill rules", text)
        self.assertIn("unless that agent already has this", text)
        self.assertIn("skill installed", text)
        self.assertIn("New projects start in solo mode: `multi_agent_enabled=false`", text)
        self.assertIn("ai-board config set multi_agent_enabled true", text)
        self.assertIn("Solo mode is the default", text)
        self.assertIn("When multi-agent mode is enabled", text)
        self.assertIn("git_integration=suggest", text)
        self.assertIn("do not run `git init`", text)
        self.assertIn("do not silently initialize git", text)
        self.assertIn("ai-board rescope T-0001", text)
        self.assertIn("unlock` keeps the task scope as history", text)
        self.assertNotIn("If an agent skill is needed", text)

    def test_readme_install_prompt_requires_skill_unless_present(self) -> None:
        chinese = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        english = (REPO_ROOT / "README_en.md").read_text(encoding="utf-8")

        self.assertIn("按该 agent 的 skill 安装方式", chinese)
        self.assertIn("除非该 agent 已经安装过这个 skill", chinese)
        self.assertNotIn("如需 agent skill", chinese)

        self.assertIn("Install the agent skill according to that agent's skill rules", english)
        self.assertIn("unless that agent already has this skill installed", english)
        self.assertNotIn("If an agent skill is needed", english)

    def test_readme_guides_human_agent_collaboration_with_prompts(self) -> None:
        chinese = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        english = (REPO_ROOT / "README_en.md").read_text(encoding="utf-8")

        self.assertIn("## 人和 AI 怎么配合", chinese)
        self.assertIn("用 ai-board 接手这个项目", chinese)
        self.assertIn("先 onboard；信息不够就问我", chinese)
        self.assertIn("把这个需求进 ai-board", chinese)
        self.assertIn("别直接开改", chinese)
        self.assertIn("看 ai-board：现在做什么？下一步做什么？", chinese)
        self.assertIn("命令细节留给 agent", chinese)

        self.assertIn("## How Humans And AI Work Together", english)
        self.assertIn("Use ai-board to take over this project", english)
        self.assertIn("If key context is missing, ask me", english)
        self.assertIn("Put this request into ai-board", english)
        self.assertIn("schedule it before coding", english)
        self.assertIn("Check ai-board: what is active", english)
        self.assertIn("The agent can use `status`, `next`, `show`, and `doctor` behind the scenes", english)

    def test_readme_documents_multi_agent_opt_in_default_off(self) -> None:
        chinese = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        english = (REPO_ROOT / "README_en.md").read_text(encoding="utf-8")

        self.assertIn("项目级可选开关，默认关闭", chinese)
        self.assertIn("ai-board config set multi_agent_enabled true", chinese)
        self.assertIn("单 agent 开发时", chinese)
        self.assertIn("处理 inbox", chinese)

        self.assertIn("Project-level opt-in, off by default", english)
        self.assertIn("ai-board config set multi_agent_enabled true", english)
        self.assertIn("In solo-agent work", english)
        self.assertIn("active-scope conflicts", english)

    def test_readme_documents_git_first_without_silent_init(self) -> None:
        chinese = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        english = (REPO_ROOT / "README_en.md").read_text(encoding="utf-8")

        self.assertIn("默认 `git_integration=suggest`", chinese)
        self.assertIn("不会静默初始化 git", chinese)
        self.assertIn("git-first 提示和 required 门禁", chinese)

        self.assertIn("Default `git_integration=suggest`", english)
        self.assertIn("does not silently initialize git", english)
        self.assertIn("Git-first hints and required gate", english)
