from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any

from .skill_guides import skill_names
from .store import PRIORITIES

CommandHandler = Callable[[argparse.Namespace], int]


def help_text(language: str, english: str, chinese: str) -> str:
    return chinese if language == "zh-CN" else english


def parser_kwargs(language: str) -> dict[str, Any]:
    return {"formatter_class": argparse.RawDescriptionHelpFormatter, "language": language}


def register_subcommands(parser: argparse.ArgumentParser, language: str, handlers: dict[str, CommandHandler]) -> None:
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser(
        "init",
        help=help_text(language, "Create a board in the project.", "创建项目看板。"),
        epilog=help_text(
            language,
            "Examples:\n  ai-board init --project-name Demo\n  ai-board init --overwrite-docs",
            "示例:\n  ai-board init --project-name Demo\n  ai-board init --overwrite-docs",
        ),
        **parser_kwargs(language),
    )
    init.add_argument("--project-name", default="", help=help_text(language, "Project display name.", "项目显示名称。"))
    init.add_argument("--force", action="store_true", help=help_text(language, "Overwrite existing board data.", "覆盖已有看板数据。"))
    init.add_argument(
        "--overwrite-docs",
        action="store_true",
        help=help_text(language, "Overwrite existing guardrail docs instead of writing .example files.", "覆盖已有规范文档，而不是写入 .example 文件。"),
    )
    init.set_defaults(func=handlers["init"])

    onboard = sub.add_parser(
        "onboard",
        help=help_text(language, "Inspect the project and print the AI-native handoff flow.", "检查项目并输出 AI 原生接手流程。"),
        epilog=help_text(
            language,
            "Examples:\n  ai-board onboard --init-if-missing\n  ai-board onboard --init-if-missing --project-name Demo",
            "示例:\n  ai-board onboard --init-if-missing\n  ai-board onboard --init-if-missing --project-name Demo",
        ),
        **parser_kwargs(language),
    )
    onboard.add_argument(
        "--init-if-missing",
        action="store_true",
        help=help_text(language, "Create the board and guardrail docs if they are missing.", "缺少看板和规范文档时自动创建。"),
    )
    onboard.add_argument(
        "--project-name",
        default="",
        help=help_text(language, "Project display name when --init-if-missing creates a board.", "--init-if-missing 创建看板时使用的项目显示名称。"),
    )
    onboard.set_defaults(func=handlers["onboard"])

    add = sub.add_parser(
        "add",
        help=help_text(language, "Add a task to inbox.", "把任务加入需求池。"),
        epilog=help_text(
            language,
            'Examples:\n  ai-board add "Write docs" --priority P1 --lane 文档治理\n  ai-board add "Build API" --acceptance "tests pass"',
            '示例:\n  ai-board add "Write docs" --priority P1 --lane 文档治理\n  ai-board add "Build API" --acceptance "tests pass"',
        ),
        **parser_kwargs(language),
    )
    add.add_argument("title")
    add.add_argument("--priority", choices=PRIORITIES, default="P2")
    add.add_argument("--description", default="")
    add.add_argument(
        "--lane",
        default=None,
        help=help_text(language, "Planning lane, for example platform, content, docs, or default.", "计划泳道，例如 platform、content、docs 或 默认。"),
    )
    add.add_argument("--source", default="", help=help_text(language, "Where this task came from.", "任务来源。"))
    add.add_argument(
        "--acceptance", action="append", default=[], help=help_text(language, "Acceptance criterion. Can be passed multiple times.", "验收标准。可以传多次。")
    )
    add.add_argument("--depends-on", nargs="*", default=[], help=help_text(language, "Task IDs this task depends on.", "该任务依赖的任务 ID。"))
    add.add_argument(
        "--verify-scope",
        nargs="*",
        default=[],
        help=help_text(language, "Paths needed for verification, for example tests or tests/test_cli.py.", "验收依赖的路径，例如 tests 或 tests/test_cli.py。"),
    )
    add.set_defaults(func=handlers["add"])

    schedule = sub.add_parser(
        "schedule",
        help=help_text(language, "Move a task to scheduled work.", "把任务排入下一批。"),
        epilog=help_text(language, "Example:\n  ai-board schedule T-0001", "示例:\n  ai-board schedule T-0001"),
        **parser_kwargs(language),
    )
    schedule.add_argument("task_id")
    schedule.set_defaults(func=handlers["schedule"])

    start = sub.add_parser(
        "start",
        help=help_text(language, "Claim a scheduled task.", "认领一个已排期任务。"),
        epilog=help_text(
            language,
            "Examples:\n  ai-board start T-0001 --agent codex-00 --scope src/ai_board/cli.py README.md\n  ai-board start T-0001 --agent codex-00 --scope docs/当前状态.md --lease-minutes 60\n\nTip: --scope is required. Keep it narrow. Prefer specific files or small subdirectories over broad roots like src, docs, tests, or .",
            "示例:\n  ai-board start T-0001 --agent codex-00 --scope src/ai_board/cli.py README.md\n  ai-board start T-0001 --agent codex-00 --scope docs/当前状态.md --lease-minutes 60\n\n提示：--scope 是必需的，并且尽量写窄。优先写具体文件或小目录，不要随手锁 src、docs、tests 或 .。",
        ),
        **parser_kwargs(language),
    )
    start.add_argument("task_id")
    start.add_argument("--agent", required=True)
    start.add_argument("--scope", nargs="*", default=[])
    start.add_argument(
        "--force", action="store_true", help=help_text(language, "Start even when scope overlaps an active task.", "即使 scope 与 active 任务重叠也启动。")
    )
    start.add_argument(
        "--lease-minutes", type=int, default=None, help=help_text(language, "Lock lease in minutes. Use 0 for no expiry.", "锁租约分钟数。0 表示不过期。")
    )
    start.set_defaults(func=handlers["start"])

    renew = sub.add_parser("renew", help=help_text(language, "Renew an active task scope lock.", "续租 active 任务的 scope 锁。"), **parser_kwargs(language))
    renew.add_argument("task_id")
    renew.add_argument("--agent", required=True)
    renew.add_argument(
        "--lease-minutes",
        type=int,
        default=None,
        help=help_text(language, "New lock lease in minutes. Use 0 for no expiry.", "新的锁租约分钟数。0 表示不过期。"),
    )
    renew.set_defaults(func=handlers["renew"])

    rescope = sub.add_parser(
        "rescope",
        help=help_text(language, "Update an active task scope and reacquire its lock.", "更新 active 任务 scope 并重新加锁。"),
        epilog=help_text(
            language,
            "Example:\n  ai-board rescope T-0001 --agent codex-00 --scope src/app.py README.md --verify-scope tests/test_app.py",
            "示例:\n  ai-board rescope T-0001 --agent codex-00 --scope src/app.py README.md --verify-scope tests/test_app.py",
        ),
        **parser_kwargs(language),
    )
    rescope.add_argument("task_id")
    rescope.add_argument("--agent", required=True)
    rescope.add_argument("--scope", nargs="*", required=True)
    rescope.add_argument("--verify-scope", nargs="*", default=None)
    rescope.add_argument(
        "--force", action="store_true", help=help_text(language, "Rescope even when another agent owns the task or scope overlaps.", "即使任务属于另一个 agent 或 scope 重叠也更新。")
    )
    rescope.add_argument(
        "--lease-minutes", type=int, default=None, help=help_text(language, "Lock lease in minutes. Use 0 for no expiry.", "锁租约分钟数。0 表示不过期。")
    )
    rescope.set_defaults(func=handlers["rescope"])

    unlock = sub.add_parser(
        "unlock",
        help=help_text(language, "Release an active task scope lock without completing the task.", "释放 active 任务的 scope 锁，但不完成任务。"),
        **parser_kwargs(language),
    )
    unlock.add_argument("task_id")
    unlock.add_argument("--agent", required=True)
    unlock.add_argument(
        "--force", action="store_true", help=help_text(language, "Unlock even when another agent owns the lock.", "即使锁属于另一个 agent 也释放。")
    )
    unlock.set_defaults(func=handlers["unlock"])

    agents = sub.add_parser("agents", help=help_text(language, "Manage reusable agent identities.", "管理可复用的 agent 身份。"), **parser_kwargs(language))
    agents_sub = agents.add_subparsers(dest="agents_command", required=True)

    agents_claim = agents_sub.add_parser(
        "claim",
        help=help_text(language, "Claim an idle agent identity, creating one if needed.", "申领空闲 agent 身份；没有就创建。"),
        **parser_kwargs(language),
    )
    agents_claim.add_argument(
        "--kind", default=None, help=help_text(language, "Agent family, for example codex or claude.", "agent 类型，例如 codex 或 claude。")
    )
    agents_claim.add_argument(
        "--lease-minutes", type=int, default=None, help=help_text(language, "Identity lease in minutes. Use 0 for no expiry.", "身份租约分钟数。0 表示不过期。")
    )
    agents_claim.set_defaults(func=handlers["agents_claim"])

    agents_list = agents_sub.add_parser(
        "list", help=help_text(language, "List registered agent identities.", "列出已注册的 agent 身份。"), **parser_kwargs(language)
    )
    agents_list.set_defaults(func=handlers["agents_list"])

    agents_release = agents_sub.add_parser(
        "release", help=help_text(language, "Release an idle or expired agent identity.", "释放空闲或过期的 agent 身份。"), **parser_kwargs(language)
    )
    agents_release.add_argument("agent_id")
    agents_release.add_argument(
        "--force",
        action="store_true",
        help=help_text(language, "Release even when the identity is attached to an active task.", "即使身份关联 active 任务也释放。"),
    )
    agents_release.set_defaults(func=handlers["agents_release"])

    complete = sub.add_parser(
        "complete",
        help=help_text(language, "Complete an active task with verification.", "完成 active 任务并写入验收结果。"),
        epilog=help_text(
            language,
            'Example:\n  ai-board complete T-0001 --verification "tests passed" --leftovers "无"',
            '示例:\n  ai-board complete T-0001 --verification "tests passed" --leftovers "无"',
        ),
        **parser_kwargs(language),
    )
    complete.add_argument("task_id")
    complete.add_argument("--verification", required=True)
    complete.add_argument("--leftovers", default="")
    complete.add_argument(
        "--deferred-verification",
        default="",
        help=help_text(language, "Full verification that must wait for another active lock.", "因其他 active 锁需要延后的全量验收说明。"),
    )
    complete.set_defaults(func=handlers["complete"])

    archive = sub.add_parser(
        "archive",
        help=help_text(language, "Archive a done task.", "归档 done 任务。"),
        epilog=help_text(language, "Example:\n  ai-board archive T-0001", "示例:\n  ai-board archive T-0001"),
        **parser_kwargs(language),
    )
    archive.add_argument("task_id")
    archive.set_defaults(func=handlers["archive"])

    reopen = sub.add_parser(
        "reopen",
        help=help_text(language, "Reopen a done or archived task.", "重新打开 done 或 archived 任务。"),
        epilog=help_text(
            language, 'Example:\n  ai-board reopen T-0001 --reason "verification found a regression"', '示例:\n  ai-board reopen T-0001 --reason "验收发现回归"'
        ),
        **parser_kwargs(language),
    )
    reopen.add_argument("task_id")
    reopen.add_argument("--reason", required=True, help=help_text(language, "Why the task needs to return to scheduled.", "任务为什么需要回到 scheduled。"))
    reopen.set_defaults(func=handlers["reopen"])

    block = sub.add_parser("block", help=help_text(language, "Mark a task blocked.", "把任务标记为 blocked。"), **parser_kwargs(language))
    block.add_argument("task_id")
    block.set_defaults(func=handlers["block"])

    goal = sub.add_parser("goal", help=help_text(language, "Set current project goal.", "设置当前项目目标。"), **parser_kwargs(language))
    goal.add_argument("goal")
    goal.set_defaults(func=handlers["goal"])

    tell = sub.add_parser(
        "tell",
        help=help_text(language, "Send a lightweight notice to another agent.", "向另一个 agent 发送轻量 notice。"),
        epilog=help_text(
            language,
            'Example:\n  ai-board tell --from codex-00 --to codex-01 --type wait --task T-0001 "waiting for tests"',
            '示例:\n  ai-board tell --from codex-00 --to codex-01 --type wait --task T-0001 "等待 tests"',
        ),
        **parser_kwargs(language),
    )
    tell.add_argument("message")
    tell.add_argument("--from", dest="sender", required=True, help=help_text(language, "Sending agent id.", "发送方 agent ID。"))
    tell.add_argument("--to", required=True, help=help_text(language, "Recipient agent id, or all.", "接收方 agent ID，或 all。"))
    tell.add_argument(
        "--type", choices=("info", "wait", "release", "handoff", "request"), default="info", help=help_text(language, "Notice type.", "notice 类型。")
    )
    tell.add_argument("--task", dest="task_id", default="", help=help_text(language, "Related task id.", "关联任务 ID。"))
    tell.set_defaults(func=handlers["tell"])

    inbox = sub.add_parser(
        "inbox", help=help_text(language, "Read or update notices for an agent.", "读取或更新某个 agent 的 notice。"), **parser_kwargs(language)
    )
    inbox.add_argument("--agent", required=True)
    inbox.add_argument("--ack", default="", help=help_text(language, "Mark a notice acknowledged.", "标记 notice 已看到。"))
    inbox.add_argument("--resolve", default="", help=help_text(language, "Mark a notice resolved.", "标记 notice 已处理。"))
    inbox.add_argument("--all", action="store_true", help=help_text(language, "Include resolved notices.", "包含已处理 notice。"))
    inbox.add_argument(
        "--fail-on-unresolved",
        action="store_true",
        help=help_text(language, "Return non-zero when unresolved notices exist.", "存在未处理 notice 时返回非零。"),
    )
    inbox.set_defaults(func=handlers["inbox"])

    config = sub.add_parser("config", help=help_text(language, "Read or update project config.", "读取或更新项目配置。"), **parser_kwargs(language))
    config_sub = config.add_subparsers(dest="config_command", required=True)

    config_list = config_sub.add_parser("list", help=help_text(language, "List project config.", "列出项目配置。"), **parser_kwargs(language))
    config_list.set_defaults(func=handlers["config_list"])

    config_get = config_sub.add_parser("get", help=help_text(language, "Print one config value.", "输出一个配置值。"), **parser_kwargs(language))
    config_get.add_argument("key")
    config_get.set_defaults(func=handlers["config_get"])

    config_set = config_sub.add_parser(
        "set", help=help_text(language, "Set one config value with validation.", "校验并设置一个配置值。"), **parser_kwargs(language)
    )
    config_set.add_argument("key")
    config_set.add_argument("value", help=help_text(language, "Use comma-separated values for list config keys.", "列表配置使用逗号分隔。"))
    config_set.set_defaults(func=handlers["config_set"])

    gate = sub.add_parser("gate", help=help_text(language, "Run scope gate checks.", "运行 scope gate 检查。"), **parser_kwargs(language))
    gate_sub = gate.add_subparsers(dest="gate_command", required=True)

    gate_pre_commit = gate_sub.add_parser(
        "pre-commit",
        help=help_text(language, "Check staged files against active task scope.", "检查 staged 文件是否落在 active 任务 scope 内。"),
        **parser_kwargs(language),
    )
    gate_pre_commit.set_defaults(func=handlers["gate_pre_commit"])

    hooks = sub.add_parser(
        "hooks",
        help=help_text(language, "Install or inspect ai-board git hooks.", "安装或检查 ai-board git hook。"),
        **parser_kwargs(language),
    )
    hooks_sub = hooks.add_subparsers(dest="hooks_command", required=True)

    hooks_install = hooks_sub.add_parser(
        "install",
        help=help_text(language, "Install an ai-board managed hook.", "安装 ai-board 托管 hook。"),
        **parser_kwargs(language),
    )
    hooks_install.add_argument("hook", choices=("pre-commit",))
    hooks_install.set_defaults(func=handlers["hooks_install"])

    hooks_status = hooks_sub.add_parser(
        "status", help=help_text(language, "Print ai-board hook status.", "输出 ai-board hook 状态。"), **parser_kwargs(language)
    )
    hooks_status.set_defaults(func=handlers["hooks_status"])

    hooks_uninstall = hooks_sub.add_parser(
        "uninstall",
        help=help_text(language, "Remove an ai-board managed hook.", "卸载 ai-board 托管 hook。"),
        **parser_kwargs(language),
    )
    hooks_uninstall.add_argument("hook", choices=("pre-commit",))
    hooks_uninstall.set_defaults(func=handlers["hooks_uninstall"])

    lang = sub.add_parser(
        "lang",
        help=help_text(language, "Print language switch commands.", "输出语言切换命令。"),
        epilog=help_text(
            language, "Examples:\n  ai-board lang zh-CN\n  ai-board lang en-US", "示例:\n  ai-board lang\n  ai-board lang zh-CN\n  ai-board lang en-US"
        ),
        **parser_kwargs(language),
    )
    lang.add_argument(
        "language",
        nargs="?",
        default="zh-CN",
        choices=("en-US", "zh-CN", "en", "zh"),
        help=help_text(language, "Language to print shell hints for. Defaults to zh-CN.", "要输出切换提示的语言。默认 zh-CN。"),
    )
    lang.set_defaults(func=handlers["lang"])

    status = sub.add_parser("status", help=help_text(language, "Print status counts.", "输出任务状态统计。"), **parser_kwargs(language))
    status.set_defaults(func=handlers["status"])

    next_work = sub.add_parser(
        "next",
        help=help_text(language, "Suggest non-conflicting next work.", "推荐不冲突的下一步。"),
        epilog=help_text(language, "Example:\n  ai-board next", "示例:\n  ai-board next"),
        **parser_kwargs(language),
    )
    next_work.add_argument(
        "--agent",
        default="",
        help=help_text(language, "Show unresolved notices for this agent before candidates.", "在候选任务前显示该 agent 的未处理 notice。"),
    )
    next_work.set_defaults(func=handlers["next"])

    conflicts = sub.add_parser(
        "conflicts", help=help_text(language, "Check active task scope conflicts.", "检查 active 任务 scope 冲突。"), **parser_kwargs(language)
    )
    conflicts.add_argument("--fail-on-conflict", action="store_true")
    conflicts.set_defaults(func=handlers["conflicts"])

    doctor = sub.add_parser("doctor", help=help_text(language, "Check project health.", "检查项目健康状态。"), **parser_kwargs(language))
    doctor.add_argument(
        "--fail-on-issue", action="store_true", help=help_text(language, "Return non-zero when an issue is found.", "发现问题时返回非零退出码。")
    )
    doctor.set_defaults(func=handlers["doctor"])

    locks = sub.add_parser("locks", help=help_text(language, "List active task scope locks.", "列出 active 任务 scope 锁。"), **parser_kwargs(language))
    locks.set_defaults(func=handlers["locks"])

    render = sub.add_parser("render", help=help_text(language, "Render Markdown docs.", "渲染 Markdown 文档。"), **parser_kwargs(language))
    render.set_defaults(func=handlers["render"])

    show = sub.add_parser(
        "show",
        help=help_text(language, "Print one task.", "输出单个任务详情。"),
        epilog=help_text(
            language,
            "Examples:\n  ai-board show T-0001\n  ai-board show T-0001 --format json",
            "示例:\n  ai-board show T-0001\n  ai-board show T-0001 --format json",
        ),
        **parser_kwargs(language),
    )
    show.add_argument("task_id")
    show.add_argument(
        "--format", choices=("human", "json"), default="human", help=help_text(language, "Output format. Defaults to human.", "输出格式。默认 human。")
    )
    show.set_defaults(func=handlers["show"])

    history = sub.add_parser("history", help=help_text(language, "Print event history.", "输出事件历史。"), **parser_kwargs(language))
    history.add_argument("task_id", nargs="?", default="", help=help_text(language, "Optional task ID to filter by.", "可选任务 ID，用于筛选历史。"))
    history.set_defaults(func=handlers["history"])

    skills = sub.add_parser(
        "skills",
        help=help_text(language, "Read AI usage guides bundled with this CLI.", "读取 CLI 内置的 AI 使用指南。"),
        epilog=help_text(
            language,
            "Examples:\n  ai-board skills\n  ai-board skills get core\n  ai-board skills get core --full",
            "示例:\n  ai-board skills\n  ai-board skills get core\n  ai-board skills get core --full",
        ),
        **parser_kwargs(language),
    )
    skills.set_defaults(func=handlers["skills_list"])
    skills_sub = skills.add_subparsers(dest="skills_command")

    skills_list = skills_sub.add_parser("list", help=help_text(language, "List bundled AI usage guides.", "列出内置 AI 使用指南。"), **parser_kwargs(language))
    skills_list.set_defaults(func=handlers["skills_list"])

    skills_get = skills_sub.add_parser(
        "get", help=help_text(language, "Print a bundled AI usage guide.", "输出一个内置 AI 使用指南。"), **parser_kwargs(language)
    )
    skills_get.add_argument("skill_name", choices=skill_names())
    skills_get.add_argument("--full", action="store_true", help=help_text(language, "Include extended command reference.", "包含扩展命令参考。"))
    skills_get.set_defaults(func=handlers["skills_get"])
