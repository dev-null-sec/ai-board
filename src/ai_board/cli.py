from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .errors import BoardError
from .guardrails import init_guardrail_docs
from .onboarding import format_onboard_result, onboard_project
from .operations import (
    add_task,
    agent_state,
    archive_task,
    claim_agent,
    complete_task,
    find_conflicts,
    list_agents,
    lock_is_expired,
    release_agent,
    renew_task_lock,
    reopen_task,
    schedule_task,
    set_goal,
    set_status,
    start_task,
    unlock_task,
)
from .parser import help_text, parser_kwargs, register_subcommands
from .render import render_archive, render_current_board, render_docs
from .skill_guides import SKILLS, get_skill, skill_names
from .store import (
    PRIORITIES,
    STATUSES,
    Paths,
    append_event,
    append_message,
    default_config,
    find_task,
    init_board,
    init_config,
    load_board,
    load_config,
    lock_is_stale,
    messages_for_agent,
    parse_iso_datetime,
    read_events,
    read_lock_metadata,
    save_config,
    update_message_status,
)

LANGUAGES = ("en-US", "zh-CN")
LANGUAGE_ALIASES = {
    "en": "en-US",
    "en-us": "en-US",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "cn": "zh-CN",
    "chinese": "zh-CN",
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def normalize_language(value: str | None) -> str:
    if value is None:
        return "en-US"
    return LANGUAGE_ALIASES.get(value.lower(), value if value in LANGUAGES else "en-US")


def language_from_argv(argv: list[str] | None = None) -> str:
    args = sys.argv[1:] if argv is None else argv
    for index, value in enumerate(args):
        if value == "--lang" and index + 1 < len(args):
            return normalize_language(args[index + 1])
        if value.startswith("--lang="):
            return normalize_language(value.split("=", 1)[1])
    return normalize_language(os.environ.get("AI_BOARD_LANG"))


def cli_language(args: argparse.Namespace) -> str:
    return normalize_language(getattr(args, "lang", None) or os.environ.get("AI_BOARD_LANG"))


def text(args: argparse.Namespace, english: str, chinese: str) -> str:
    return chinese if cli_language(args) == "zh-CN" else english


def localize_board_error(args: argparse.Namespace, message: str) -> str:
    if cli_language(args) != "zh-CN":
        return message
    if message.startswith("Task scope is required."):
        return "任务 scope 是必需的。请使用具体文件或小目录，例如 --scope src/app.py README.md。"
    if message.startswith("Scope path contains spaces and does not exist:"):
        return message.replace(
            "Scope path contains spaces and does not exist:",
            "scope 路径包含空格且该路径不存在：",
            1,
        ).replace(
            "If you meant multiple paths, pass each path as a separate --scope argument; if this is one path with spaces, create it first or check the spelling.",
            "如果你想传多个路径，请把每个路径作为单独的 --scope 参数；如果这是一个带空格的路径，请先创建它或检查拼写。",
        )
    if message.startswith("Unknown config key:"):
        return message.replace("Unknown config key:", "未知配置项：", 1)
    if "dependencies are not complete" in message:
        return message.replace("dependencies are not complete", "依赖任务尚未完成")
    return message


def translate_argparse_message(message: str) -> str:
    replacements = {
        "the following arguments are required:": "缺少必填参数:",
        "invalid choice:": "无效选项:",
        "choose from": "可选值",
        "expected one argument": "需要一个值",
        "unrecognized arguments:": "无法识别的参数:",
        "argument": "参数",
    }
    for english, chinese in replacements.items():
        message = message.replace(english, chinese)
    return message


class LocalizedArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, language: str = "en-US", **kwargs: Any) -> None:
        self.output_language = language
        super().__init__(*args, **kwargs)

    def format_help(self) -> str:
        help_output = self.localize_argparse_output(super().format_help())
        return help_output

    def format_usage(self) -> str:
        return self.localize_argparse_output(super().format_usage())

    def localize_argparse_output(self, help_output: str) -> str:
        if self.output_language != "zh-CN":
            return help_output
        replacements = {
            "usage:": "用法:",
            "positional arguments:": "位置参数:",
            "options:": "选项:",
            "optional arguments:": "选项:",
            "show this help message and exit": "显示帮助信息并退出",
        }
        for english, chinese in replacements.items():
            help_output = help_output.replace(english, chinese)
        return help_output

    def error(self, message: str) -> None:
        if self.output_language != "zh-CN":
            super().error(message)
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: 错误: {translate_argparse_message(message)}\n")


def root_path(args: argparse.Namespace) -> Path:
    return Path(args.root).expanduser().resolve()


def config_value(args: argparse.Namespace, key: str) -> Any:
    return load_config(root_path(args))[key]


def multi_agent_enabled(args: argparse.Namespace) -> bool:
    return bool(config_value(args, "multi_agent_enabled"))


def detect_git_state(root: Path) -> tuple[str, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=5,
            check=False,
        )
    except FileNotFoundError:
        return ("missing", "")
    except subprocess.TimeoutExpired:
        return ("error", "git command timed out")
    if result.returncode == 0:
        return ("ok", (result.stdout or "").strip())
    message = (result.stderr or result.stdout or "").strip()
    return ("none", message)


def git_onboard_notice(args: argparse.Namespace, root: Path) -> str:
    mode = str(config_value(args, "git_integration"))
    if mode == "off":
        return ""
    state, detail = detect_git_state(root)
    if state == "ok":
        return ""
    if state == "missing":
        return text(
            args,
            "\nGit is not available. Install git before AI-managed development if you want rollback checkpoints.",
            "\n当前环境找不到 git。若希望 AI 开发可随时回滚，请先安装 git。",
        )
    if mode == "required":
        return text(
            args,
            "\nGit is required for this project but is not initialized. Before coding, confirm the project root, run `git init`, add a .gitignore, and make an initial commit. ai-board will not do this silently.",
            "\n当前项目要求使用 git，但尚未初始化。编码前请先确认项目根目录，运行 `git init`，补充 .gitignore，并创建初始提交。ai-board 不会静默执行这些操作。",
        )
    suffix = f" ({detail})" if detail else ""
    return text(
        args,
        f"\nGit is not initialized for this project{suffix}. Recommended before coding: confirm the project root, run `git init`, add a .gitignore, and make an initial commit. ai-board will not do this silently.",
        f"\n当前项目尚未初始化 git{suffix}。建议编码前先确认项目根目录，运行 `git init`，补充 .gitignore，并创建初始提交。ai-board 不会静默执行这些操作。",
    )


def parse_config_value(key: str, value: str) -> Any:
    defaults = default_config()
    if key not in defaults:
        raise BoardError(f"Unknown config key: {key}")
    if isinstance(defaults[key], bool):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "yes", "on", "enabled"):
            return True
        if normalized in ("0", "false", "no", "off", "disabled"):
            return False
        raise BoardError(f"Config key {key} must be true or false.")
    if isinstance(defaults[key], int):
        try:
            return int(value)
        except ValueError as error:
            raise BoardError(f"Config key {key} must be a number.") from error
    if isinstance(defaults[key], list):
        if not value.strip():
            return []
        return [item.strip() for item in value.split(",") if item.strip()]
    if key == "git_integration":
        return value.strip().lower()
    return value


def print_config_value(key: str, value: Any) -> None:
    if isinstance(value, bool):
        print(f"{key}: {str(value).lower()}")
        return
    if isinstance(value, list):
        print(f"{key}: {', '.join(str(item) for item in value)}")
    else:
        print(f"{key}: {value}")


def print_notice(message: dict[str, Any]) -> None:
    status = "resolved" if message.get("resolved_at") else "acknowledged" if message.get("acknowledged_at") else "new"
    task_text = f" task={message.get('task_id')}" if message.get("task_id") else ""
    print(f"- {message.get('id')} [{message.get('type')}] {status} from={message.get('from')} to={message.get('to')}{task_text}: {message.get('message')}")


def print_agent_notices(args: argparse.Namespace, limit: int = 5) -> None:
    if not multi_agent_enabled(args):
        return
    agent = getattr(args, "agent", "") or ""
    if not agent:
        return
    notices = messages_for_agent(root_path(args), agent)
    if not notices:
        return
    print("")
    print(text(args, f"Notices for {agent}:", f"{agent} 的 notice："))
    for message in notices[:limit]:
        print_notice(message)
    if len(notices) > limit:
        print(
            text(
                args,
                f"- ... {len(notices) - limit} more; run `ai-board inbox --agent {agent}`",
                f"- ... 还有 {len(notices) - limit} 条；运行 `ai-board inbox --agent {agent}` 查看",
            )
        )


def print_unresolved_notice_warning(args: argparse.Namespace, agent: str, limit: int = 3) -> None:
    if not multi_agent_enabled(args):
        return
    if not agent:
        return
    notices = messages_for_agent(root_path(args), agent)
    if not notices:
        return
    print("")
    print(
        text(
            args,
            f"warning: {agent} still has unresolved notices; run `ai-board inbox --agent {agent}`.",
            f"警告：{agent} 仍有未处理 notice；请运行 `ai-board inbox --agent {agent}`。",
        )
    )
    for message in notices[:limit]:
        print_notice(message)
    if len(notices) > limit:
        print(text(args, f"- ... {len(notices) - limit} more", f"- ... 还有 {len(notices) - limit} 条"))


def print_task(task: dict[str, Any]) -> None:
    print(f"{task['id']} [{task['status']}] {task.get('priority', 'P2')} {task['title']}")


def format_value(value: Any, args: argparse.Namespace | None = None) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else text(args, "none", "无") if args else "none"
    return str(value) if value not in ("", None) else text(args, "none", "无") if args else "none"


def print_task_detail(task: dict[str, Any], args: argparse.Namespace) -> None:
    print_task(task)
    print(f"{text(args, 'lane', '泳道')}: {format_value(task.get('lane'), args)}")
    print(f"{text(args, 'owner', '负责人')}: {format_value(task.get('owner_agent'), args)}")
    print(f"{text(args, 'scope', '范围')}: {format_value(task.get('scope', []), args)}")
    print(f"{text(args, 'verify_scope', '验证范围')}: {format_value(task.get('verify_scope', []), args)}")
    print(f"{text(args, 'source', '来源')}: {format_value(task.get('source'), args)}")
    print(f"{text(args, 'depends_on', '依赖')}: {format_value(task.get('depends_on', []), args)}")
    description = task.get("description")
    if description:
        print(f"{text(args, 'description', '描述')}: {description}")
    acceptance = task.get("acceptance", [])
    if acceptance:
        print(f"{text(args, 'acceptance', '验收标准')}:")
        for item in acceptance:
            print(f"- {item}")
    verification = task.get("verification")
    if verification:
        print(f"{text(args, 'verification', '验收结果')}: {verification}")
    deferred_verification = task.get("deferred_verification")
    if deferred_verification:
        print(f"{text(args, 'deferred_verification', '延后验收')}: {deferred_verification}")
    leftovers = task.get("leftovers")
    if leftovers:
        print(f"{text(args, 'leftovers', '遗留问题')}: {leftovers}")


def print_agent(agent: dict[str, Any], args: argparse.Namespace | None = None) -> None:
    state = agent.get("state") or agent.get("status") or "idle"
    lease = agent.get("lease_expires_at") or format_value("", args)
    task_id = agent.get("task_id") or format_value("", args)
    print(
        f"{agent['id']} [{state}] "
        f"{text(args, 'kind', '类型')}={agent.get('kind', '')} "
        f"{text(args, 'task', '任务')}={task_id} "
        f"{text(args, 'lease_expires_at', '租约到期')}={lease}"
    )


def format_onboard_lock_notice(board: dict[str, Any], args: argparse.Namespace) -> str:
    active_tasks = [task for task in board.get("tasks", []) if task.get("status") == "active" and task.get("scope")]
    if not active_tasks:
        return ""
    lines = ["", text(args, "Active task scope locks:", "当前 active task scope 锁：")]
    for task in active_tasks:
        owner = task.get("lock_owner") or task.get("owner_agent") or text(args, "unknown", "未知")
        lease = task.get("lease_expires_at") or text(args, "none", "无")
        scope = ", ".join(str(item) for item in task.get("scope", []))
        state = text(args, "expired", "已过期") if lock_is_expired(task) else text(args, "active", "有效")
        lines.append(
            f"- {task['id']} "
            f"{text(args, 'owner', '负责人')}={owner} "
            f"{text(args, 'lock', '锁')}={state} "
            f"{text(args, 'lease_expires_at', '租约到期')}={lease} "
            f"{text(args, 'scope', '范围')}={scope}"
        )
        if lock_is_expired(task):
            lines.append(text(args, "  lease is expired; coordinate before taking over this scope.", "  租约已过期；接管这些 scope 前先确认并协调。"))
        else:
            lines.append(
                text(
                    args,
                    f"  if you are not {owner}, do not edit this scope; wait, pick non-overlapping scheduled work, or coordinate a takeover.",
                    f"  如果你不是 {owner}，不要修改这些 scope；请等待、选择不冲突的已排期任务，或先协调接管。",
                )
            )
    return "\n".join(lines)


def active_task_detail(task: dict[str, Any], args: argparse.Namespace) -> str:
    owner = task.get("lock_owner") or task.get("owner_agent") or text(args, "unknown", "未知")
    lease = task.get("lease_expires_at") or text(args, "none", "无")
    scope = ", ".join(str(item) for item in task.get("scope", [])) or text(args, "none", "无")
    return f"{task['id']} {text(args, 'owner', '负责人')}={owner} {text(args, 'lease_expires_at', '租约到期')}={lease} {text(args, 'scope', '范围')}={scope}"


def ensure_task_is_not_active_for_command(root: Path, task_id: str, command_name: str, args: argparse.Namespace) -> None:
    board = load_board(root)
    task = find_task(board, task_id)
    if task.get("status") != "active":
        return
    raise BoardError(
        text(
            args,
            f"Task {task_id} is already active; do not {command_name} it again. {active_task_detail(task, args)}",
            f"任务 {task_id} 已经是 active，不要再次执行 {command_name}。{active_task_detail(task, args)}",
        )
    )


def docs_stale_messages(root: Path, board: dict[str, Any], args: argparse.Namespace) -> list[str]:
    paths = Paths(root)
    language = str(load_config(root)["language"])
    expected_docs = {
        paths.current_board_doc: render_current_board(board, language),
        paths.archive_doc: render_archive(board, language),
    }
    messages: list[str] = []
    for doc_path, expected in expected_docs.items():
        if not doc_path.exists():
            messages.append(
                text(
                    args,
                    f"generated doc missing: {doc_path}; trust JSON and run ai-board render",
                    f"生成看板缺失：{doc_path}；请以 JSON 为准并运行 ai-board render",
                )
            )
            continue
        try:
            actual = doc_path.read_text(encoding="utf-8")
        except OSError as error:
            messages.append(
                text(
                    args,
                    f"generated doc unreadable: {doc_path} ({error}); trust JSON and run ai-board render",
                    f"生成看板无法读取：{doc_path}（{error}）；请以 JSON 为准并运行 ai-board render",
                )
            )
            continue
        if actual != expected:
            messages.append(
                text(
                    args,
                    f"generated doc stale: {doc_path}; trust JSON and run ai-board render",
                    f"生成看板已过期：{doc_path}；请以 JSON 为准并运行 ai-board render",
                )
            )
    return messages


def candidate_status_rank(task: dict[str, Any]) -> int:
    return {"scheduled": 0, "inbox": 1}.get(str(task.get("status")), 2)


def priority_rank(task: dict[str, Any]) -> int:
    return {priority: index for index, priority in enumerate(PRIORITIES)}.get(str(task.get("priority", "P2")), len(PRIORITIES))


def scopes_overlap_for_next(left: str, right: str) -> bool:
    if left == right:
        return True
    left_prefix = f"{left.rstrip('/')}/"
    right_prefix = f"{right.rstrip('/')}/"
    return left.startswith(right_prefix) or right.startswith(left_prefix)


def task_scopes_overlap_active(scopes: list[str], active_tasks: list[dict[str, Any]]) -> bool:
    for active_task in active_tasks:
        for locked_scope in active_task.get("scope", []):
            for scope in scopes:
                if scopes_overlap_for_next(str(locked_scope), str(scope)):
                    return True
    return False


def format_verify_scope_conflicts(verify_scope: list[str], active_tasks: list[dict[str, Any]]) -> list[str]:
    conflicts: list[str] = []
    for active_task in active_tasks:
        for locked_scope in active_task.get("scope", []):
            for scope in verify_scope:
                if scopes_overlap_for_next(str(locked_scope), str(scope)):
                    conflicts.append(f"{active_task['id']} {locked_scope} <-> {scope}")
    return conflicts


def task_matches_scopes(task_scopes: list[str], target_scopes: list[str]) -> list[str]:
    matches: list[str] = []
    for task_scope in task_scopes:
        for target_scope in target_scopes:
            if scopes_overlap_for_next(str(task_scope), str(target_scope)):
                matches.append(f"{task_scope} <-> {target_scope}")
    return matches


def next_candidate_note(args: argparse.Namespace, task: dict[str, Any], locked_active: list[dict[str, Any]]) -> tuple[str, str]:
    scope = task.get("scope") or []
    verify_scope = task.get("verify_scope") or []
    if not scope:
        state = "needs-scope"
        note = text(args, "needs scope before conflict check", "需要先声明 scope 后再判断是否冲突")
    elif task_scopes_overlap_active(scope, locked_active):
        state = "blocked-by-active-lock"
        note = text(args, "overlaps active lock; do not start unless coordinated", "与 active 锁重叠；未协调前不要 start")
    else:
        state = "available"
        note = text(args, "appears non-overlapping", "看起来不冲突")
    verify_conflicts = format_verify_scope_conflicts(verify_scope, locked_active)
    if verify_conflicts:
        if state == "available":
            state = "verification-waiting"
        note += text(args, f"; verify scope waits on active lock ({'; '.join(verify_conflicts)})", f"；验证范围等待 active 锁（{'; '.join(verify_conflicts)}）")
    elif not verify_scope:
        note += text(args, "; verify scope undeclared", "；未声明验证范围")
    return state, note


def print_next_action_advice(args: argparse.Namespace, states: list[str], locked_active: list[dict[str, Any]]) -> None:
    if not multi_agent_enabled(args):
        return
    if not locked_active:
        return
    print("")
    print(text(args, "Next action advice:", "下一步动作建议："))
    if "available" in states:
        print(text(args, "- Start an available non-overlapping scheduled task before waiting.", "- 优先 start 一个不冲突的 scheduled 任务，不要直接等待。"))
    if "needs-scope" in states:
        print(
            text(
                args,
                "- For needs-scope candidates, declare a narrow scope first, then rerun `ai-board next`.",
                "- 对需要 scope 的候选，先声明窄 scope，再重新运行 `ai-board next`。",
            )
        )
    if "blocked-by-active-lock" in states:
        print(
            text(
                args,
                "- For blocked candidates, coordinate with the owner or split out read-only evaluation/docs work in a separate task.",
                "- 对被 active 锁阻塞的候选，先协调 owner，或拆出只读评估/文档任务单独推进。",
            )
        )
    if "verification-waiting" in states:
        print(
            text(
                args,
                "- If only verification is blocked, record local checks and deferred full verification instead of pretending the full suite ran.",
                "- 如果只是验证范围被阻塞，记录局部检查和延后全量验收，不要假装已跑完整验证。",
            )
        )
    print(
        text(
            args,
            "- Pause only after checking for safe non-overlapping work and documenting why none is available.",
            "- 只有确认没有安全的不冲突工作，并记录原因后，才暂停。",
        )
    )


def cmd_init(args: argparse.Namespace) -> int:
    board = init_board(root_path(args), args.project_name, args.force)
    init_config(root_path(args), args.force)
    written_docs = init_guardrail_docs(root_path(args), args.overwrite_docs)
    render_docs(root_path(args), board)
    print(f"initialized: {root_path(args)}")
    print(f"guardrail docs: {len(written_docs)}")
    print("next: ai-board onboard")
    return 0


def cmd_onboard(args: argparse.Namespace) -> int:
    root = root_path(args)
    result = onboard_project(root, args.project_name, args.init_if_missing)
    print(format_onboard_result(result))
    git_notice = git_onboard_notice(args, root)
    if git_notice:
        print(git_notice)
    if multi_agent_enabled(args):
        notice = format_onboard_lock_notice(load_board(root), args)
        if notice:
            print(notice)
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    lane = args.lane if args.lane is not None else config_value(args, "default_lane")
    task = add_task(root_path(args), args.title, args.priority, args.description, lane, args.source, args.acceptance, args.depends_on, args.verify_scope)
    print_task(task)
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    root = root_path(args)
    ensure_task_is_not_active_for_command(root, args.task_id, "schedule", args)
    task = schedule_task(root, args.task_id)
    print_task(task)
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    root = root_path(args)
    ensure_task_is_not_active_for_command(root, args.task_id, "start", args)
    lease_minutes = args.lease_minutes if args.lease_minutes is not None else int(config_value(args, "default_lease_minutes"))
    task = start_task(root, args.task_id, args.agent, args.scope, args.force, lease_minutes, enforce_scope_conflicts=multi_agent_enabled(args))
    print_task(task)
    return 0


def cmd_renew(args: argparse.Namespace) -> int:
    lease_minutes = args.lease_minutes if args.lease_minutes is not None else int(config_value(args, "default_lease_minutes"))
    task = renew_task_lock(root_path(args), args.task_id, args.agent, lease_minutes)
    print_task(task)
    return 0


def cmd_unlock(args: argparse.Namespace) -> int:
    task = unlock_task(root_path(args), args.task_id, args.agent, args.force)
    print_task(task)
    return 0


def cmd_agents_claim(args: argparse.Namespace) -> int:
    kind = args.kind if args.kind is not None else str(config_value(args, "default_agent_kind"))
    lease_minutes = args.lease_minutes if args.lease_minutes is not None else int(config_value(args, "default_lease_minutes"))
    agent = claim_agent(root_path(args), kind, lease_minutes)
    print_agent(agent, args)
    return 0


def cmd_agents_list(args: argparse.Namespace) -> int:
    agents = list_agents(root_path(args))
    if not agents:
        print(text(args, "no agents", "暂无 agent"))
        return 0
    for agent in agents:
        print_agent(agent, args)
    return 0


def cmd_agents_release(args: argparse.Namespace) -> int:
    agent = release_agent(root_path(args), args.agent_id, args.force)
    print_agent(agent, args)
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    task = complete_task(root_path(args), args.task_id, args.verification, args.leftovers, args.deferred_verification)
    print_task(task)
    print_unresolved_notice_warning(args, str(task.get("owner_agent") or ""))
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    task = archive_task(root_path(args), args.task_id)
    print_task(task)
    print_unresolved_notice_warning(args, str(task.get("owner_agent") or ""))
    return 0


def cmd_reopen(args: argparse.Namespace) -> int:
    task = reopen_task(root_path(args), args.task_id, args.reason)
    print_task(task)
    return 0


def cmd_block(args: argparse.Namespace) -> int:
    task = set_status(root_path(args), args.task_id, "blocked")
    print_task(task)
    return 0


def cmd_goal(args: argparse.Namespace) -> int:
    board = set_goal(root_path(args), args.goal)
    print(f"goal: {board.get('project', {}).get('current_goal', '')}")
    return 0


def cmd_config_list(args: argparse.Namespace) -> int:
    config = load_config(root_path(args))
    for key in sorted(config):
        print_config_value(key, config[key])
    return 0


def cmd_config_get(args: argparse.Namespace) -> int:
    config = load_config(root_path(args))
    if args.key not in config:
        raise BoardError(f"Unknown config key: {args.key}")
    print_config_value(args.key, config[args.key])
    return 0


def cmd_config_set(args: argparse.Namespace) -> int:
    value = parse_config_value(args.key, args.value)
    config = save_config(root_path(args), {args.key: value})
    append_event(root_path(args), "config.set", data={"key": args.key, "value": config[args.key]})
    render_docs(root_path(args), load_board(root_path(args)))
    print_config_value(args.key, config[args.key])
    print(text(args, "rendered docs", "已渲染文档"))
    return 0


def cmd_tell(args: argparse.Namespace) -> int:
    message = append_message(root_path(args), args.sender, args.to, args.type, args.task_id, args.message)
    print_notice(message)
    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    root = root_path(args)
    if args.ack:
        print_notice(update_message_status(root, args.ack, args.agent, resolve=False))
        return 0
    if args.resolve:
        print_notice(update_message_status(root, args.resolve, args.agent, resolve=True))
        return 0
    notices = messages_for_agent(root, args.agent, args.all)
    unresolved_notices = messages_for_agent(root, args.agent)
    if not notices:
        print(text(args, "no notices", "暂无 notice"))
        return 0
    for message in notices:
        print_notice(message)
    if args.fail_on_unresolved and unresolved_notices:
        print(text(args, f"unresolved notices: {len(unresolved_notices)}", f"未处理 notice 数量：{len(unresolved_notices)}"))
        return 1
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    board = load_board(root_path(args))
    counts = {status: 0 for status in STATUSES}
    for task in board["tasks"]:
        counts[task["status"]] += 1
    counts["archived"] = len(board["archive"])
    print(f"{text(args, 'project', '项目')}: {board.get('project', {}).get('name') or root_path(args).name}")
    for status in STATUSES:
        print(f"{status}: {counts[status]}")
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    root = root_path(args)
    board = load_board(root)
    active = [task for task in board["tasks"] if task["status"] == "active" and task.get("scope")]
    multi_agent = multi_agent_enabled(args)
    print(text(args, "Current active locks:", "当前 active 锁："))
    if active:
        for task in active:
            state = text(args, "expired", "已过期") if lock_is_expired(task) else text(args, "active", "有效")
            print(f"- {active_task_detail(task, args)} {text(args, 'lock', '锁')}={state}")
            if not lock_is_expired(task):
                owner = task.get("lock_owner") or task.get("owner_agent") or text(args, "unknown", "未知")
                print(
                    text(
                        args,
                        f"  if you are not {owner}, do not operate this task or edit its scope.",
                        f"  如果你不是 {owner}，不要操作这个任务，也不要修改它的 scope。",
                    )
                )
    else:
        print(text(args, "- none", "- 无"))

    stale_messages = docs_stale_messages(root, board, args)
    if stale_messages:
        print("")
        print(text(args, "Generated board warning:", "生成看板提醒："))
        for message in stale_messages:
            print(f"- {message}")

    waiting = [task for task in board["tasks"] if task["status"] in ("done", "active") and task.get("deferred_verification")]
    if waiting:
        print("")
        print(text(args, "Waiting for full verification:", "等待全量验收："))
        for task in sorted(waiting, key=lambda item: str(item.get("id", ""))):
            print(f"- {task['id']} [{task['status']}] {task['title']} - {task.get('deferred_verification')}")

    print_agent_notices(args)

    candidates = [task for task in board["tasks"] if task["status"] in ("scheduled", "inbox")]
    candidates.sort(key=lambda task: (candidate_status_rank(task), priority_rank(task), str(task.get("id", ""))))
    print("")
    print(text(args, "Candidate next work:", "候选下一步："))
    if not candidates:
        print(text(args, "- no scheduled or inbox tasks", "- 没有 scheduled 或 inbox 任务"))
        return 0
    locked_active = [task for task in active if not lock_is_expired(task)] if multi_agent else []
    candidate_states: list[str] = []
    for task in candidates:
        state, note = next_candidate_note(args, task, locked_active)
        candidate_states.append(state)
        print(f"- {task['id']} [{task['status']}] {task.get('priority', 'P2')} {task['title']} - {state}: {note}")
    print_next_action_advice(args, candidate_states, locked_active)
    return 0


def cmd_conflicts(args: argparse.Namespace) -> int:
    board = load_board(root_path(args))
    conflicts = find_conflicts(board)
    if not conflicts:
        print("no conflicts")
        return 0
    for left, right, scope in conflicts:
        print(f"{left['id']} ({left.get('owner_agent')}) conflicts with {right['id']} ({right.get('owner_agent')}) on {scope}")
    return 1 if args.fail_on_conflict else 0


def cmd_doctor(args: argparse.Namespace) -> int:
    root = root_path(args)
    paths = Paths(root)
    issues: list[str] = []
    config = load_config(root)
    git_mode = str(config["git_integration"])
    multi_agent = bool(config["multi_agent_enabled"])
    now = datetime.now(timezone.utc)
    stale_active_delta = timedelta(hours=int(config["doctor_stale_active_hours"]))
    lease_warning_delta = timedelta(minutes=int(config["doctor_lease_warning_minutes"]))
    broad_scopes = set(str(item).strip() for item in config["doctor_broad_scopes"] if str(item).strip())
    shared_scopes = [str(item).strip() for item in config["shared_verification_scopes"] if str(item).strip()]
    shared_scope_warning_delta = timedelta(minutes=int(config["shared_scope_warning_minutes"]))
    if paths.lock_file.exists():
        stale, reason = lock_is_stale(paths.lock_file)
        metadata = read_lock_metadata(paths.lock_file)
        if stale:
            issues.append(
                text(
                    args,
                    f"stale board lock: {reason}; run a write command to auto-clear it or remove {paths.lock_file}",
                    f"board 锁已过期：{reason}；运行一次写命令自动清理，或删除 {paths.lock_file}",
                )
            )
        else:
            print(text(args, f"board lock: active {metadata}", f"board 锁：占用中 {metadata}"))
    else:
        print(text(args, "board lock: ok", "board 锁：正常"))

    if git_mode == "off":
        print(text(args, "git: skipped", "git：已跳过"))
    else:
        git_state, git_detail = detect_git_state(root)
        if git_state == "ok":
            print(text(args, "git: ok", "git：正常"))
        elif git_mode == "required":
            if git_state == "missing":
                issues.append(text(args, "git is required but the git command was not found", "当前项目要求使用 git，但找不到 git 命令"))
            else:
                suffix = f": {git_detail}" if git_detail else ""
                issues.append(
                    text(
                        args,
                        f"git is required but this project is not initialized as a git work tree{suffix}; run git init only after confirming the project root",
                        f"当前项目要求使用 git，但这里不是 git 工作区{suffix}；确认项目根目录后再运行 git init",
                    )
                )
        elif git_state == "missing":
            print(text(args, "git: recommended, but git command was not found", "git：建议使用，但当前找不到 git 命令"))
        else:
            print(
                text(
                    args,
                    "git: recommended, not initialized; confirm the project root before running git init",
                    "git：建议使用，但尚未初始化；运行 git init 前请先确认项目根目录",
                )
            )

    board: dict[str, Any] | None = None
    try:
        board = load_board(root)
    except BoardError as error:
        issues.append(
            text(
                args,
                f"board: {error}; fix .ai-board/board.json or restore it from version control",
                f"board：{error}；请修复 .ai-board/board.json 或从版本控制恢复",
            )
        )

    if board is not None:
        print(text(args, "board schema: ok", "board 结构：正常"))
        agents = {agent["id"]: agent for agent in board.get("agents", [])}
        for task in board["tasks"]:
            if task["status"] != "active":
                continue
            task_id = task["id"]
            if not task.get("owner_agent"):
                issues.append(
                    text(
                        args,
                        f"active task {task_id} has no owner_agent; start it with --agent or fix the board",
                        f"active 任务 {task_id} 没有 owner_agent；请用 --agent 启动，或修复 board",
                    )
                )
            scope = task.get("scope") or []
            if not scope:
                issues.append(
                    text(
                        args,
                        f"active task {task_id} has no scope; set an honest scope or unlock it",
                        f"active 任务 {task_id} 没有 scope；请设置真实 scope，或释放锁",
                    )
                )
            elif any(item in broad_scopes for item in scope):
                issues.append(
                    text(
                        args,
                        f"active task {task_id} scope is broad ({', '.join(scope)}); prefer specific files or smaller subdirectories",
                        f"active 任务 {task_id} 的 scope 过宽（{', '.join(scope)}）；优先使用具体文件或更小目录",
                    )
                )
            if not task.get("acceptance"):
                issues.append(
                    text(
                        args,
                        f"active task {task_id} has no acceptance criteria; add concrete acceptance before continuing",
                        f"active 任务 {task_id} 没有验收标准；继续前请补充具体验收",
                    )
                )
            updated_at = parse_iso_datetime(str(task.get("updated_at") or task.get("started_at") or ""))
            if updated_at is not None and now - updated_at >= stale_active_delta:
                issues.append(
                    text(
                        args,
                        f"active task {task_id} has not been updated for {int(config['doctor_stale_active_hours'])}+ hours; renew, complete, block, or archive it",
                        f"active 任务 {task_id} 已超过 {int(config['doctor_stale_active_hours'])} 小时未更新；请 renew、complete、block 或 archive",
                    )
                )
            locked_at = parse_iso_datetime(str(task.get("locked_at") or task.get("started_at") or ""))
            shared_matches = task_matches_scopes(scope, shared_scopes)
            if shared_matches and locked_at is not None and now - locked_at >= shared_scope_warning_delta:
                issues.append(
                    text(
                        args,
                        f"active task {task_id} holds shared verification scope ({', '.join(shared_matches)}); release it promptly because other tasks may be waiting for full verification",
                        f"active 任务 {task_id} 占用了共享验证 scope（{', '.join(shared_matches)}）；请尽快释放，因为其他任务可能在等待全量验收",
                    )
                )
            owner = task.get("owner_agent") or ""
            agent = agents.get(owner)
            if multi_agent and owner and agent is None:
                issues.append(
                    text(
                        args,
                        f"active task {task_id} owner {owner} is not registered; run ai-board agents claim or fix agents",
                        f"active 任务 {task_id} 的 owner {owner} 未注册；请运行 ai-board agents claim 或修复 agents",
                    )
                )
            elif multi_agent and agent is not None and agent.get("task_id") not in ("", task_id):
                issues.append(
                    text(
                        args,
                        f"agent {owner} points to {agent.get('task_id')} but active task is {task_id}; release or reclaim the identity",
                        f"agent {owner} 指向 {agent.get('task_id')}，但 active 任务是 {task_id}；请释放或重新认领身份",
                    )
                )
            elif multi_agent and agent is not None and agent_state(agent) == "expired":
                issues.append(
                    text(
                        args,
                        f"agent {owner} lease is expired; run ai-board agents claim or ai-board renew {task_id} --agent {owner}",
                        f"agent {owner} 租约已过期；请运行 ai-board agents claim 或 ai-board renew {task_id} --agent {owner}",
                    )
                )
            elif multi_agent and agent is not None:
                lease_expires_at = parse_iso_datetime(str(agent.get("lease_expires_at") or ""))
                if lease_expires_at is not None and lease_expires_at <= now + lease_warning_delta:
                    issues.append(
                        text(
                            args,
                            f"agent {owner} lease expires soon; run ai-board renew {task_id} --agent {owner}",
                            f"agent {owner} 租约即将过期；请运行 ai-board renew {task_id} --agent {owner}",
                        )
                    )

        conflicts = find_conflicts(board)
        if multi_agent and conflicts:
            for left, right, scope in conflicts:
                issues.append(
                    text(
                        args,
                        f"scope conflict: {left['id']} and {right['id']} overlap on {scope}; coordinate, unlock, or narrow scope",
                        f"scope 冲突：{left['id']} 和 {right['id']} 在 {scope} 上重叠；请协调、释放锁或缩小 scope",
                    )
                )
        else:
            print(text(args, "scope conflicts: ok", "scope 冲突：正常"))

        language = str(load_config(root)["language"])
        expected_docs = {
            paths.current_board_doc: render_current_board(board, language),
            paths.archive_doc: render_archive(board, language),
        }
        for doc_path, expected in expected_docs.items():
            if not doc_path.exists():
                issues.append(f"generated doc missing: {doc_path}; run ai-board render")
                continue
            try:
                actual = doc_path.read_text(encoding="utf-8")
            except OSError as error:
                issues.append(f"generated doc unreadable: {doc_path} ({error}); check file permissions")
                continue
            if actual != expected:
                issues.append(f"generated doc stale: {doc_path}; run ai-board render")
        if not any("generated doc" in issue for issue in issues):
            print(text(args, "generated docs: ok", "生成文档：正常"))

    try:
        events = read_events(root)
    except BoardError as error:
        issues.append(f"event log: {error}; fix or move .ai-board/events.jsonl")
    else:
        print(text(args, f"event log: ok ({len(events)} events)", f"事件日志：正常（{len(events)} 条）"))
    if paths.failed_events_file.exists():
        issues.append(f"event log fallback: {paths.failed_events_file} exists; investigate why event writes failed")

    if issues:
        for issue in issues:
            print(f"{text(args, 'issue', '问题')}: {issue}")
        return 1 if args.fail_on_issue else 0
    print(text(args, "doctor: ok", "doctor：正常"))
    return 0


def cmd_locks(args: argparse.Namespace) -> int:
    board = load_board(root_path(args))
    active = [task for task in board["tasks"] if task["status"] == "active" and task.get("scope")]
    if not active:
        print(text(args, "no locks", "暂无锁"))
        return 0
    for task in active:
        owner = task.get("lock_owner") or task.get("owner_agent") or "unknown"
        locked_at = task.get("locked_at") or task.get("started_at") or ""
        lease = task.get("lease_expires_at") or "none"
        state = "expired" if lock_is_expired(task) else "active"
        scope = ", ".join(task.get("scope", []))
        print(
            f"{task['id']} {owner} "
            f"{text(args, 'lock', '锁')}={state} "
            f"{text(args, 'locked_at', '锁定时间')}={locked_at} "
            f"{text(args, 'lease_expires_at', '租约到期')}={lease} "
            f"{text(args, 'scope', '范围')}={scope}"
        )
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    board = load_board(root_path(args))
    render_docs(root_path(args), board)
    print("rendered docs")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    board = load_board(root_path(args))
    task = find_task(board, args.task_id)
    if args.format == "json":
        print(json.dumps(task, ensure_ascii=False, indent=2))
    else:
        print_task_detail(task, args)
    return 0


def cmd_lang(args: argparse.Namespace) -> int:
    language = args.language
    if language == "en":
        language = "en-US"
    if language == "zh":
        language = "zh-CN"
    print(f"Language / 语言: {language}")
    print("PowerShell:")
    print(f'  $env:AI_BOARD_LANG="{language}"')
    print("cmd.exe:")
    print(f"  set AI_BOARD_LANG={language}")
    print("bash/zsh:")
    print(f"  export AI_BOARD_LANG={language}")
    print("One-shot / 单次运行:")
    print(f"  ai-board --lang {language} status")
    return 0


def format_history_event(event: dict[str, Any]) -> str:
    created_at = event.get("created_at") or "unknown-time"
    action = event.get("action") or "unknown-action"
    task_id = event.get("task_id") or "-"
    agent = event.get("agent") or "-"
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    parts = [f"{created_at} {action}", f"task={task_id}", f"agent={agent}"]
    status = data.get("status")
    if status:
        parts.append(f"status={status}")
    scope = data.get("scope")
    if isinstance(scope, list) and scope:
        parts.append("scope=" + ",".join(str(item) for item in scope))
    title = data.get("title")
    if title:
        parts.append(f"title={title}")
    return " | ".join(parts)


def cmd_history(args: argparse.Namespace) -> int:
    events = read_events(root_path(args), args.task_id or "")
    if not events:
        target = f" for {args.task_id}" if args.task_id else ""
        print(f"no history{target}")
        return 0
    for event in events:
        print(format_history_event(event))
    return 0


def cmd_skills_list(args: argparse.Namespace) -> int:
    for name in skill_names():
        print(f"{name}  {SKILLS[name]['description']}")
    return 0


def cmd_skills_get(args: argparse.Namespace) -> int:
    print(get_skill(args.skill_name, args.full))
    return 0


def build_parser(argv: list[str] | None = None) -> argparse.ArgumentParser:
    language = language_from_argv(argv)
    parser = LocalizedArgumentParser(prog="ai-board", **parser_kwargs(language))
    parser.add_argument("--root", default=".", help=help_text(language, "Project root. Defaults to current directory.", "项目根目录。默认当前目录。"))
    parser.add_argument(
        "--lang",
        choices=LANGUAGES,
        default=None,
        help=help_text(language, "Human output language. Defaults to AI_BOARD_LANG or en-US.", "人类可读输出语言。默认读取 AI_BOARD_LANG，未设置时为 en-US。"),
    )
    register_subcommands(
        parser,
        language,
        {
            "init": cmd_init,
            "onboard": cmd_onboard,
            "add": cmd_add,
            "schedule": cmd_schedule,
            "start": cmd_start,
            "renew": cmd_renew,
            "unlock": cmd_unlock,
            "agents_claim": cmd_agents_claim,
            "agents_list": cmd_agents_list,
            "agents_release": cmd_agents_release,
            "complete": cmd_complete,
            "archive": cmd_archive,
            "reopen": cmd_reopen,
            "block": cmd_block,
            "goal": cmd_goal,
            "tell": cmd_tell,
            "inbox": cmd_inbox,
            "config_list": cmd_config_list,
            "config_get": cmd_config_get,
            "config_set": cmd_config_set,
            "lang": cmd_lang,
            "status": cmd_status,
            "next": cmd_next,
            "conflicts": cmd_conflicts,
            "doctor": cmd_doctor,
            "locks": cmd_locks,
            "render": cmd_render,
            "show": cmd_show,
            "history": cmd_history,
            "skills_list": cmd_skills_list,
            "skills_get": cmd_skills_get,
        },
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser(argv)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BoardError as error:
        print(localize_board_error(args, str(error)), file=sys.stderr)
        return 1
