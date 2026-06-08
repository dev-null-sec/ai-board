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
        self.assertIn("First 60 Seconds", core_text)
        self.assertIn("ai-board skills get core --full", core_text)

        full_output = io.StringIO()
        with redirect_stdout(full_output):
            self.assertEqual(main(["skills", "get", "core", "--full"]), 0)
        full_text = full_output.getvalue()
        self.assertIn("[--fail-on-unresolved]", full_text)
        self.assertIn("inbox --agent codex-01 --fail-on-unresolved", full_text)
        self.assertIn("If it returns non-zero, do not finish", full_text)
        self.assertIn("failed handoff", full_text)

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
        full_output = io.StringIO()
        with redirect_stdout(full_output):
            self.assertEqual(main(["skills", "get", "core", "--full"]), 0)
        full_text = full_output.getvalue()

        self.assertLess(len(text.splitlines()), 120)
        self.assertGreater(len(full_text.splitlines()), len(text.splitlines()) * 3)
        self.assertIn("First 60 Seconds", text)
        self.assertIn("ai-board onboard --init-if-missing", text)
        self.assertIn("ai-board next", text)
        self.assertIn("honest, narrow", text)
        self.assertIn("broad roots", text)
        self.assertIn("Directory names, file names", text)
        self.assertIn("small evidence fragments are", text)
        self.assertIn("Do not write final roadmap language", text)
        self.assertIn("Install the agent skill according to that agent's skill rules", text)
        self.assertIn("unless that agent already has this", text)
        self.assertIn("skill installed", text)
        self.assertIn("Solo mode is the default: `multi_agent_enabled=false`", text)
        self.assertIn("ai-board config set multi_agent_enabled true", text)
        self.assertIn("Solo mode is the default", text)
        self.assertIn("When multi-agent mode is enabled", text)
        self.assertIn("git_integration=suggest", text)
        self.assertIn("it does not run `git init` for you", text)
        self.assertIn("Do not silently initialize git", text)
        self.assertIn("scope_gate", text)
        self.assertIn("ai-board hooks status", text)
        self.assertIn("ai-board gate pre-commit", text)
        self.assertIn("not runtime file blocking", text)
        self.assertIn("ai-board rescope T-0001", text)
        self.assertIn("unlock` keeps the task scope as history", text)
        self.assertIn("Do not archive by age alone", text)
        self.assertIn("If the project direction changed", text)
        self.assertIn("ai-board archive TASK_ID", text)
        self.assertIn("ai-board reopen TASK_ID --reason TEXT", text)
        self.assertIn("Do not hand-edit", text)
        self.assertIn("docs/计划看板.md", text)
        self.assertIn("ai-board bookkeeping writes", text)
        self.assertIn("not extra business scope", text)
        self.assertIn("ai-board skills get core --full", text)
        self.assertIn("When you receive a notice", full_text)
        self.assertIn("scope_gate=required", full_text)
        self.assertIn("--no-verify", full_text)
        self.assertIn("ai-board hooks uninstall pre-commit", full_text)
        self.assertIn("do not add them to every task scope", full_text)
        self.assertIn("Command reference", full_text)
        self.assertNotIn("If an agent skill is needed", text)

    def test_readme_keeps_ai_install_and_onboard_entry_short(self) -> None:
        chinese = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        english = (REPO_ROOT / "README_en.md").read_text(encoding="utf-8")

        self.assertIn("安装：", chinese)
        self.assertIn("pipx install ai-board", chinese)
        self.assertIn("接手项目：", chinese)
        self.assertIn("ai-board onboard --init-if-missing", chinese)
        self.assertNotIn("如需 agent skill", chinese)

        self.assertIn("Install:", english)
        self.assertIn("pipx install ai-board", english)
        self.assertIn("Onboard:", english)
        self.assertIn("ai-board onboard --init-if-missing", english)
        self.assertNotIn("If an agent skill is needed", english)

    def test_readme_guides_human_agent_collaboration_with_prompts(self) -> None:
        chinese = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        english = (REPO_ROOT / "README_en.md").read_text(encoding="utf-8")

        self.assertIn("不是保险箱", chinese)
        self.assertIn("逼 AI 先记账再动手", chinese)
        self.assertIn("先把需求进看板、声明 scope，再开始动代码", chinese)
        self.assertIn("这次为什么改、打算改哪些文件、改完怎么验收", chinese)
        self.assertIn("任务、scope 和 git diff", chinese)
        self.assertIn("scope gate 是个 git pre-commit 钩子", chinese)
        self.assertIn("它拦的是 commit 不是 AI 动手", chinese)
        self.assertIn("接手项目：", chinese)
        self.assertIn("用 ai-board 接手这个项目", chinese)
        self.assertIn("把这个需求进 ai-board。如果不属于当前任务就排期", chinese)
        self.assertIn("ai-board 现在什么状态？下一步做什么？", chinese)

        self.assertIn("addresses a blind spot in vibe coding", english)
        self.assertIn("AI must not infer project direction on its own", english)
        self.assertIn("Every code change must belong to a task", english)
        self.assertIn("Multiple agents must not step on each other", english)
        self.assertIn('"Done" must mean something verifiable', english)
        self.assertIn("every change should belong to a task with declared scope", english)
        self.assertIn("The CLI can't physically stop an AI from editing a file", english)
        self.assertIn("### For humans", english)
        self.assertIn("### For AI agents (Claude, Codex, etc.)", english)
        self.assertIn("Use ai-board to onboard this project", english)
        self.assertIn("An empty project won't start coding", english)
        self.assertIn("Put this request into ai-board", english)
        self.assertIn("what scope to declare, and what acceptance criteria to set", english)
        self.assertIn("What's the status in ai-board? What's next?", english)

    def test_readme_documents_multi_agent_opt_in_default_off(self) -> None:
        chinese = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        english = (REPO_ROOT / "README_en.md").read_text(encoding="utf-8")

        self.assertIn("ai-board config set multi_agent_enabled true", chinese)
        self.assertIn("单 agent 默认模式", chinese)
        self.assertIn("强制多 agent 流程", chinese)
        self.assertIn("scope 重叠会被拦住", chinese)

        self.assertIn("ai-board config set multi_agent_enabled true", english)
        self.assertIn("Single-agent mode doesn't enforce any of this", english)
        self.assertIn("No notices, no conflicts", english)
        self.assertIn("scope conflicts and blocked candidates", english)

    def test_readme_documents_git_first_without_silent_init(self) -> None:
        chinese = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        english = (REPO_ROOT / "README_en.md").read_text(encoding="utf-8")

        self.assertIn("git pre-commit 钩子", chinese)
        self.assertIn("提交关口", chinese)
        self.assertIn("git commit --no-verify", chinese)
        self.assertIn("git diff", chinese)

        self.assertIn("it depends on it", english)
        self.assertIn("suggests commits before coding", english)
        self.assertIn("git_integration=required", english)
        self.assertIn("Silent `git init` / `git commit`", english)

    def test_readme_documents_scope_gate_as_commit_gate(self) -> None:
        chinese = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        english = (REPO_ROOT / "README_en.md").read_text(encoding="utf-8")

        self.assertIn("scope gate 是个 git pre-commit 钩子", chinese)
        self.assertIn("提交关口", chinese)
        self.assertIn("它拦的是 commit 不是 AI 动手", chinese)
        self.assertIn("--no-verify", chinese)
        self.assertIn("运行时文件拦截", chinese)

        self.assertIn("ai-board gate pre-commit", english)
        self.assertIn("scope_gate=required", english)
        self.assertIn("commit-time gate", english)
        self.assertIn("not runtime file interception", english)
        self.assertIn("--no-verify", english)
        self.assertIn("does not overwrite", english)

    def test_readme_explains_board_side_effects_are_not_business_scope(self) -> None:
        chinese = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        english = (REPO_ROOT / "README_en.md").read_text(encoding="utf-8")

        self.assertIn("`.ai-board/board.json`", chinese)
        self.assertIn("唯一数据源", chinese)
        self.assertIn("JSON 是机器读的，Markdown 是人读的", chinese)
        self.assertIn("写入永远走 CLI", chinese)

        self.assertIn("`.ai-board/board.json`", english)
        self.assertIn("Single source of truth", english)
        self.assertIn("JSON is for machines. Markdown is for humans.", english)
        self.assertIn("Writes always go through the CLI", english)
