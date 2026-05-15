from __future__ import annotations

import argparse
import json
import os
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
    schedule_task,
    set_goal,
    set_status,
    start_task,
    unlock_task,
)
from .render import render_archive, render_current_board, render_docs
from .skill_guides import SKILLS, get_skill, skill_names
from .store import (
    PRIORITIES,
    STATUSES,
    Paths,
    find_task,
    init_board,
    init_config,
    load_board,
    load_config,
    lock_is_stale,
    parse_iso_datetime,
    read_events,
    read_lock_metadata,
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


def help_text(language: str, english: str, chinese: str) -> str:
    return chinese if language == "zh-CN" else english


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
    return (
        f"{task['id']} "
        f"{text(args, 'owner', '负责人')}={owner} "
        f"{text(args, 'lease_expires_at', '租约到期')}={lease} "
        f"{text(args, 'scope', '范围')}={scope}"
    )


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
            messages.append(text(args, f"generated doc missing: {doc_path}; trust JSON and run ai-board render", f"生成看板缺失：{doc_path}；请以 JSON 为准并运行 ai-board render"))
            continue
        try:
            actual = doc_path.read_text(encoding="utf-8")
        except OSError as error:
            messages.append(text(args, f"generated doc unreadable: {doc_path} ({error}); trust JSON and run ai-board render", f"生成看板无法读取：{doc_path}（{error}）；请以 JSON 为准并运行 ai-board render"))
            continue
        if actual != expected:
            messages.append(text(args, f"generated doc stale: {doc_path}; trust JSON and run ai-board render", f"生成看板已过期：{doc_path}；请以 JSON 为准并运行 ai-board render"))
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


def candidate_overlaps_active(candidate: dict[str, Any], active_tasks: list[dict[str, Any]]) -> bool:
    for active_task in active_tasks:
        for locked_scope in active_task.get("scope", []):
            for candidate_scope in candidate.get("scope", []):
                if scopes_overlap_for_next(str(locked_scope), str(candidate_scope)):
                    return True
    return False


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
    notice = format_onboard_lock_notice(load_board(root), args)
    if notice:
        print(notice)
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    lane = args.lane if args.lane is not None else config_value(args, "default_lane")
    task = add_task(root_path(args), args.title, args.priority, args.description, lane, args.source, args.acceptance, args.depends_on)
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
    task = start_task(root, args.task_id, args.agent, args.scope, args.force, lease_minutes)
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
    task = complete_task(root_path(args), args.task_id, args.verification, args.leftovers)
    print_task(task)
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    task = archive_task(root_path(args), args.task_id)
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
    print(text(args, "Current active locks:", "当前 active 锁："))
    if active:
        for task in active:
            state = text(args, "expired", "已过期") if lock_is_expired(task) else text(args, "active", "有效")
            print(f"- {active_task_detail(task, args)} {text(args, 'lock', '锁')}={state}")
            if not lock_is_expired(task):
                owner = task.get("lock_owner") or task.get("owner_agent") or text(args, "unknown", "未知")
                print(text(args, f"  if you are not {owner}, do not operate this task or edit its scope.", f"  如果你不是 {owner}，不要操作这个任务，也不要修改它的 scope。"))
    else:
        print(text(args, "- none", "- 无"))

    stale_messages = docs_stale_messages(root, board, args)
    if stale_messages:
        print("")
        print(text(args, "Generated board warning:", "生成看板提醒："))
        for message in stale_messages:
            print(f"- {message}")

    candidates = [task for task in board["tasks"] if task["status"] in ("scheduled", "inbox")]
    candidates.sort(key=lambda task: (candidate_status_rank(task), priority_rank(task), str(task.get("id", ""))))
    print("")
    print(text(args, "Candidate next work:", "候选下一步："))
    if not candidates:
        print(text(args, "- no scheduled or inbox tasks", "- 没有 scheduled 或 inbox 任务"))
        return 0
    locked_active = [task for task in active if not lock_is_expired(task)]
    for task in candidates:
        scope = task.get("scope") or []
        if not scope:
            note = text(args, "needs scope before conflict check", "需要先声明 scope 后再判断是否冲突")
        elif candidate_overlaps_active(task, locked_active):
            note = text(args, "overlaps active lock; do not start unless coordinated", "与 active 锁重叠；未协调前不要 start")
        else:
            note = text(args, "appears non-overlapping", "看起来不冲突")
        print(f"- {task['id']} [{task['status']}] {task.get('priority', 'P2')} {task['title']} - {note}")
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
    now = datetime.now(timezone.utc)
    stale_active_delta = timedelta(hours=int(config["doctor_stale_active_hours"]))
    lease_warning_delta = timedelta(minutes=int(config["doctor_lease_warning_minutes"]))
    broad_scopes = set(str(item).strip() for item in config["doctor_broad_scopes"] if str(item).strip())
    if paths.lock_file.exists():
        stale, reason = lock_is_stale(paths.lock_file)
        metadata = read_lock_metadata(paths.lock_file)
        if stale:
            issues.append(text(args, f"stale board lock: {reason}; run a write command to auto-clear it or remove {paths.lock_file}", f"board 锁已过期：{reason}；运行一次写命令自动清理，或删除 {paths.lock_file}"))
        else:
            print(text(args, f"board lock: active {metadata}", f"board 锁：占用中 {metadata}"))
    else:
        print(text(args, "board lock: ok", "board 锁：正常"))

    board: dict[str, Any] | None = None
    try:
        board = load_board(root)
    except BoardError as error:
        issues.append(text(args, f"board: {error}; fix .ai-board/board.json or restore it from version control", f"board：{error}；请修复 .ai-board/board.json 或从版本控制恢复"))

    if board is not None:
        print(text(args, "board schema: ok", "board 结构：正常"))
        agents = {agent["id"]: agent for agent in board.get("agents", [])}
        for task in board["tasks"]:
            if task["status"] != "active":
                continue
            task_id = task["id"]
            if not task.get("owner_agent"):
                issues.append(f"active task {task_id} has no owner_agent; start it with --agent or fix the board")
            scope = task.get("scope") or []
            if not scope:
                issues.append(f"active task {task_id} has no scope; set an honest scope or unlock it")
            elif any(item in broad_scopes for item in scope):
                issues.append(f"active task {task_id} scope is broad ({', '.join(scope)}); prefer specific files or smaller subdirectories")
            if not task.get("acceptance"):
                issues.append(f"active task {task_id} has no acceptance criteria; add concrete acceptance before continuing")
            updated_at = parse_iso_datetime(str(task.get("updated_at") or task.get("started_at") or ""))
            if updated_at is not None and now - updated_at >= stale_active_delta:
                issues.append(f"active task {task_id} has not been updated for {int(config['doctor_stale_active_hours'])}+ hours; renew, complete, block, or archive it")
            owner = task.get("owner_agent") or ""
            agent = agents.get(owner)
            if owner and agent is None:
                issues.append(f"active task {task_id} owner {owner} is not registered; run ai-board agents claim or fix agents")
            elif agent is not None and agent.get("task_id") not in ("", task_id):
                issues.append(f"agent {owner} points to {agent.get('task_id')} but active task is {task_id}; release or reclaim the identity")
            elif agent is not None and agent_state(agent) == "expired":
                issues.append(f"agent {owner} lease is expired; run ai-board agents claim or ai-board renew {task_id} --agent {owner}")
            elif agent is not None:
                lease_expires_at = parse_iso_datetime(str(agent.get("lease_expires_at") or ""))
                if lease_expires_at is not None and lease_expires_at <= now + lease_warning_delta:
                    issues.append(f"agent {owner} lease expires soon; run ai-board renew {task_id} --agent {owner}")

        conflicts = find_conflicts(board)
        if conflicts:
            for left, right, scope in conflicts:
                issues.append(f"scope conflict: {left['id']} and {right['id']} overlap on {scope}; coordinate, unlock, or narrow scope")
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


def parser_kwargs(language: str) -> dict[str, Any]:
    return {"formatter_class": argparse.RawDescriptionHelpFormatter, "language": language}


def build_parser(argv: list[str] | None = None) -> argparse.ArgumentParser:
    language = language_from_argv(argv)
    parser = LocalizedArgumentParser(prog="ai-board", **parser_kwargs(language))
    parser.add_argument("--root", default=".", help=help_text(language, "Project root. Defaults to current directory.", "项目根目录。默认当前目录。"))
    parser.add_argument("--lang", choices=LANGUAGES, default=None, help=help_text(language, "Human output language. Defaults to AI_BOARD_LANG or en-US.", "人类可读输出语言。默认读取 AI_BOARD_LANG，未设置时为 en-US。"))
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser(
        "init",
        help=help_text(language, "Create a board in the project.", "创建项目看板。"),
        epilog=help_text(language, "Examples:\n  ai-board init --project-name Demo\n  ai-board init --overwrite-docs", "示例:\n  ai-board init --project-name Demo\n  ai-board init --overwrite-docs"),
        **parser_kwargs(language),
    )
    init.add_argument("--project-name", default="", help=help_text(language, "Project display name.", "项目显示名称。"))
    init.add_argument("--force", action="store_true", help=help_text(language, "Overwrite existing board data.", "覆盖已有看板数据。"))
    init.add_argument("--overwrite-docs", action="store_true", help=help_text(language, "Overwrite existing guardrail docs instead of writing .example files.", "覆盖已有规范文档，而不是写入 .example 文件。"))
    init.set_defaults(func=cmd_init)

    onboard = sub.add_parser(
        "onboard",
        help=help_text(language, "Inspect the project and print the AI-native handoff flow.", "检查项目并输出 AI 原生接手流程。"),
        epilog=help_text(language, "Examples:\n  ai-board onboard --init-if-missing\n  ai-board onboard --init-if-missing --project-name Demo", "示例:\n  ai-board onboard --init-if-missing\n  ai-board onboard --init-if-missing --project-name Demo"),
        **parser_kwargs(language),
    )
    onboard.add_argument("--init-if-missing", action="store_true", help=help_text(language, "Create the board and guardrail docs if they are missing.", "缺少看板和规范文档时自动创建。"))
    onboard.add_argument("--project-name", default="", help=help_text(language, "Project display name when --init-if-missing creates a board.", "--init-if-missing 创建看板时使用的项目显示名称。"))
    onboard.set_defaults(func=cmd_onboard)

    add = sub.add_parser(
        "add",
        help=help_text(language, "Add a task to inbox.", "把任务加入需求池。"),
        epilog=help_text(language, 'Examples:\n  ai-board add "Write docs" --priority P1 --lane 文档治理\n  ai-board add "Build API" --acceptance "tests pass"', '示例:\n  ai-board add "Write docs" --priority P1 --lane 文档治理\n  ai-board add "Build API" --acceptance "tests pass"'),
        **parser_kwargs(language),
    )
    add.add_argument("title")
    add.add_argument("--priority", choices=PRIORITIES, default="P2")
    add.add_argument("--description", default="")
    add.add_argument("--lane", default=None, help=help_text(language, "Planning lane, for example platform, content, docs, or default.", "计划泳道，例如 platform、content、docs 或 默认。"))
    add.add_argument("--source", default="", help=help_text(language, "Where this task came from.", "任务来源。"))
    add.add_argument("--acceptance", action="append", default=[], help=help_text(language, "Acceptance criterion. Can be passed multiple times.", "验收标准。可以传多次。"))
    add.add_argument("--depends-on", nargs="*", default=[], help=help_text(language, "Task IDs this task depends on.", "该任务依赖的任务 ID。"))
    add.set_defaults(func=cmd_add)

    schedule = sub.add_parser(
        "schedule",
        help=help_text(language, "Move a task to scheduled work.", "把任务排入下一批。"),
        epilog=help_text(language, "Example:\n  ai-board schedule T-0001", "示例:\n  ai-board schedule T-0001"),
        **parser_kwargs(language),
    )
    schedule.add_argument("task_id")
    schedule.set_defaults(func=cmd_schedule)

    start = sub.add_parser(
        "start",
        help=help_text(language, "Claim a scheduled task.", "认领一个已排期任务。"),
        epilog=help_text(language, "Examples:\n  ai-board start T-0001 --agent codex-00 --scope src/ai_board/cli.py README.md\n  ai-board start T-0001 --agent codex-00 --scope docs/当前状态.md --lease-minutes 60\n\nTip: keep --scope narrow. Prefer specific files or small subdirectories over broad roots like src, docs, tests, or .", "示例:\n  ai-board start T-0001 --agent codex-00 --scope src/ai_board/cli.py README.md\n  ai-board start T-0001 --agent codex-00 --scope docs/当前状态.md --lease-minutes 60\n\n提示：--scope 尽量写窄。优先写具体文件或小目录，不要随手锁 src、docs、tests 或 .。"),
        **parser_kwargs(language),
    )
    start.add_argument("task_id")
    start.add_argument("--agent", required=True)
    start.add_argument("--scope", nargs="*", default=[])
    start.add_argument("--force", action="store_true", help=help_text(language, "Start even when scope overlaps an active task.", "即使 scope 与 active 任务重叠也启动。"))
    start.add_argument("--lease-minutes", type=int, default=None, help=help_text(language, "Lock lease in minutes. Use 0 for no expiry.", "锁租约分钟数。0 表示不过期。"))
    start.set_defaults(func=cmd_start)

    renew = sub.add_parser("renew", help=help_text(language, "Renew an active task scope lock.", "续租 active 任务的 scope 锁。"), **parser_kwargs(language))
    renew.add_argument("task_id")
    renew.add_argument("--agent", required=True)
    renew.add_argument("--lease-minutes", type=int, default=None, help=help_text(language, "New lock lease in minutes. Use 0 for no expiry.", "新的锁租约分钟数。0 表示不过期。"))
    renew.set_defaults(func=cmd_renew)

    unlock = sub.add_parser("unlock", help=help_text(language, "Release an active task scope lock without completing the task.", "释放 active 任务的 scope 锁，但不完成任务。"), **parser_kwargs(language))
    unlock.add_argument("task_id")
    unlock.add_argument("--agent", required=True)
    unlock.add_argument("--force", action="store_true", help=help_text(language, "Unlock even when another agent owns the lock.", "即使锁属于另一个 agent 也释放。"))
    unlock.set_defaults(func=cmd_unlock)

    agents = sub.add_parser("agents", help=help_text(language, "Manage reusable agent identities.", "管理可复用的 agent 身份。"), **parser_kwargs(language))
    agents_sub = agents.add_subparsers(dest="agents_command", required=True)

    agents_claim = agents_sub.add_parser("claim", help=help_text(language, "Claim an idle agent identity, creating one if needed.", "申领空闲 agent 身份；没有就创建。"), **parser_kwargs(language))
    agents_claim.add_argument("--kind", default=None, help=help_text(language, "Agent family, for example codex or claude.", "agent 类型，例如 codex 或 claude。"))
    agents_claim.add_argument("--lease-minutes", type=int, default=None, help=help_text(language, "Identity lease in minutes. Use 0 for no expiry.", "身份租约分钟数。0 表示不过期。"))
    agents_claim.set_defaults(func=cmd_agents_claim)

    agents_list = agents_sub.add_parser("list", help=help_text(language, "List registered agent identities.", "列出已注册的 agent 身份。"), **parser_kwargs(language))
    agents_list.set_defaults(func=cmd_agents_list)

    agents_release = agents_sub.add_parser("release", help=help_text(language, "Release an idle or expired agent identity.", "释放空闲或过期的 agent 身份。"), **parser_kwargs(language))
    agents_release.add_argument("agent_id")
    agents_release.add_argument("--force", action="store_true", help=help_text(language, "Release even when the identity is attached to an active task.", "即使身份关联 active 任务也释放。"))
    agents_release.set_defaults(func=cmd_agents_release)

    complete = sub.add_parser(
        "complete",
        help=help_text(language, "Complete an active task with verification.", "完成 active 任务并写入验收结果。"),
        epilog=help_text(language, 'Example:\n  ai-board complete T-0001 --verification "tests passed" --leftovers "无"', '示例:\n  ai-board complete T-0001 --verification "tests passed" --leftovers "无"'),
        **parser_kwargs(language),
    )
    complete.add_argument("task_id")
    complete.add_argument("--verification", required=True)
    complete.add_argument("--leftovers", default="")
    complete.set_defaults(func=cmd_complete)

    archive = sub.add_parser(
        "archive",
        help=help_text(language, "Archive a done task.", "归档 done 任务。"),
        epilog=help_text(language, "Example:\n  ai-board archive T-0001", "示例:\n  ai-board archive T-0001"),
        **parser_kwargs(language),
    )
    archive.add_argument("task_id")
    archive.set_defaults(func=cmd_archive)

    block = sub.add_parser("block", help=help_text(language, "Mark a task blocked.", "把任务标记为 blocked。"), **parser_kwargs(language))
    block.add_argument("task_id")
    block.set_defaults(func=cmd_block)

    goal = sub.add_parser("goal", help=help_text(language, "Set current project goal.", "设置当前项目目标。"), **parser_kwargs(language))
    goal.add_argument("goal")
    goal.set_defaults(func=cmd_goal)

    lang = sub.add_parser(
        "lang",
        help=help_text(language, "Print language switch commands.", "输出语言切换命令。"),
        epilog=help_text(language, "Examples:\n  ai-board lang zh-CN\n  ai-board lang en-US", "示例:\n  ai-board lang\n  ai-board lang zh-CN\n  ai-board lang en-US"),
        **parser_kwargs(language),
    )
    lang.add_argument("language", nargs="?", default="zh-CN", choices=("en-US", "zh-CN", "en", "zh"), help=help_text(language, "Language to print shell hints for. Defaults to zh-CN.", "要输出切换提示的语言。默认 zh-CN。"))
    lang.set_defaults(func=cmd_lang)

    status = sub.add_parser("status", help=help_text(language, "Print status counts.", "输出任务状态统计。"), **parser_kwargs(language))
    status.set_defaults(func=cmd_status)

    next_work = sub.add_parser(
        "next",
        help=help_text(language, "Suggest non-conflicting next work.", "推荐不冲突的下一步。"),
        epilog=help_text(language, "Example:\n  ai-board next", "示例:\n  ai-board next"),
        **parser_kwargs(language),
    )
    next_work.set_defaults(func=cmd_next)

    conflicts = sub.add_parser("conflicts", help=help_text(language, "Check active task scope conflicts.", "检查 active 任务 scope 冲突。"), **parser_kwargs(language))
    conflicts.add_argument("--fail-on-conflict", action="store_true")
    conflicts.set_defaults(func=cmd_conflicts)

    doctor = sub.add_parser("doctor", help=help_text(language, "Check project health.", "检查项目健康状态。"), **parser_kwargs(language))
    doctor.add_argument("--fail-on-issue", action="store_true", help=help_text(language, "Return non-zero when an issue is found.", "发现问题时返回非零退出码。"))
    doctor.set_defaults(func=cmd_doctor)

    locks = sub.add_parser("locks", help=help_text(language, "List active task scope locks.", "列出 active 任务 scope 锁。"), **parser_kwargs(language))
    locks.set_defaults(func=cmd_locks)

    render = sub.add_parser("render", help=help_text(language, "Render Markdown docs.", "渲染 Markdown 文档。"), **parser_kwargs(language))
    render.set_defaults(func=cmd_render)

    show = sub.add_parser(
        "show",
        help=help_text(language, "Print one task.", "输出单个任务详情。"),
        epilog=help_text(language, "Examples:\n  ai-board show T-0001\n  ai-board show T-0001 --format json", "示例:\n  ai-board show T-0001\n  ai-board show T-0001 --format json"),
        **parser_kwargs(language),
    )
    show.add_argument("task_id")
    show.add_argument("--format", choices=("human", "json"), default="human", help=help_text(language, "Output format. Defaults to human.", "输出格式。默认 human。"))
    show.set_defaults(func=cmd_show)

    history = sub.add_parser("history", help=help_text(language, "Print event history.", "输出事件历史。"), **parser_kwargs(language))
    history.add_argument("task_id", nargs="?", default="", help=help_text(language, "Optional task ID to filter by.", "可选任务 ID，用于筛选历史。"))
    history.set_defaults(func=cmd_history)

    skills = sub.add_parser(
        "skills",
        help=help_text(language, "Read AI usage guides bundled with this CLI.", "读取 CLI 内置的 AI 使用指南。"),
        epilog=help_text(language, "Examples:\n  ai-board skills\n  ai-board skills get core\n  ai-board skills get core --full", "示例:\n  ai-board skills\n  ai-board skills get core\n  ai-board skills get core --full"),
        **parser_kwargs(language),
    )
    skills.set_defaults(func=cmd_skills_list)
    skills_sub = skills.add_subparsers(dest="skills_command")

    skills_list = skills_sub.add_parser("list", help=help_text(language, "List bundled AI usage guides.", "列出内置 AI 使用指南。"), **parser_kwargs(language))
    skills_list.set_defaults(func=cmd_skills_list)

    skills_get = skills_sub.add_parser("get", help=help_text(language, "Print a bundled AI usage guide.", "输出一个内置 AI 使用指南。"), **parser_kwargs(language))
    skills_get.add_argument("skill_name", choices=skill_names())
    skills_get.add_argument("--full", action="store_true", help=help_text(language, "Include extended command reference.", "包含扩展命令参考。"))
    skills_get.set_defaults(func=cmd_skills_get)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser(argv)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BoardError as error:
        print(str(error), file=sys.stderr)
        return 1
