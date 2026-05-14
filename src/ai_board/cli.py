from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .guardrails import init_guardrail_docs
from .onboarding import format_onboard_result, onboard_project
from .operations import (
    DEFAULT_LEASE_MINUTES,
    add_task,
    agent_state,
    archive_task,
    claim_agent,
    complete_task,
    find_conflicts,
    list_agents,
    lock_is_expired,
    renew_task_lock,
    release_agent,
    schedule_task,
    set_goal,
    set_status,
    start_task,
    unlock_task,
)
from .render import render_archive, render_current_board, render_docs
from .skill_guides import SKILLS, get_skill, skill_names
from .store import PRIORITIES, STATUSES, find_task, init_board, load_board, read_events
from .store import Paths, lock_is_stale, read_lock_metadata


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def root_path(args: argparse.Namespace) -> Path:
    return Path(args.root).expanduser().resolve()


def print_task(task: dict[str, Any]) -> None:
    print(f"{task['id']} [{task['status']}] {task.get('priority', 'P2')} {task['title']}")


def print_agent(agent: dict[str, Any]) -> None:
    state = agent.get("state") or agent.get("status") or "idle"
    lease = agent.get("lease_expires_at") or "none"
    task_id = agent.get("task_id") or "none"
    print(f"{agent['id']} [{state}] kind={agent.get('kind', '')} task={task_id} lease_expires_at={lease}")


def cmd_init(args: argparse.Namespace) -> int:
    board = init_board(root_path(args), args.project_name, args.force)
    written_docs = init_guardrail_docs(root_path(args), args.overwrite_docs)
    render_docs(root_path(args), board)
    print(f"initialized: {root_path(args)}")
    print(f"guardrail docs: {len(written_docs)}")
    print("next: ai-board onboard")
    return 0


def cmd_onboard(args: argparse.Namespace) -> int:
    result = onboard_project(root_path(args), args.project_name, args.init_if_missing)
    print(format_onboard_result(result))
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    task = add_task(root_path(args), args.title, args.priority, args.description, args.lane, args.source, args.acceptance, args.depends_on)
    print_task(task)
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    task = schedule_task(root_path(args), args.task_id)
    print_task(task)
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    task = start_task(root_path(args), args.task_id, args.agent, args.scope, args.force, args.lease_minutes)
    print_task(task)
    return 0


def cmd_renew(args: argparse.Namespace) -> int:
    task = renew_task_lock(root_path(args), args.task_id, args.agent, args.lease_minutes)
    print_task(task)
    return 0


def cmd_unlock(args: argparse.Namespace) -> int:
    task = unlock_task(root_path(args), args.task_id, args.agent, args.force)
    print_task(task)
    return 0


def cmd_agents_claim(args: argparse.Namespace) -> int:
    agent = claim_agent(root_path(args), args.kind, args.lease_minutes)
    print_agent(agent)
    return 0


def cmd_agents_list(args: argparse.Namespace) -> int:
    agents = list_agents(root_path(args))
    if not agents:
        print("no agents")
        return 0
    for agent in agents:
        print_agent(agent)
    return 0


def cmd_agents_release(args: argparse.Namespace) -> int:
    agent = release_agent(root_path(args), args.agent_id, args.force)
    print_agent(agent)
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
    print(f"project: {board.get('project', {}).get('name') or root_path(args).name}")
    for status in STATUSES:
        print(f"{status}: {counts[status]}")
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
    if paths.lock_file.exists():
        stale, reason = lock_is_stale(paths.lock_file)
        metadata = read_lock_metadata(paths.lock_file)
        if stale:
            issues.append(f"stale board lock: {reason}; run a write command to auto-clear it or remove {paths.lock_file}")
        else:
            print(f"board lock: active {metadata}")
    else:
        print("board lock: ok")

    board: dict[str, Any] | None = None
    try:
        board = load_board(root)
    except SystemExit as error:
        issues.append(f"board: {error}; fix .ai-board/board.json or restore it from version control")

    if board is not None:
        print("board schema: ok")
        agents = {agent["id"]: agent for agent in board.get("agents", [])}
        for task in board["tasks"]:
            if task["status"] != "active":
                continue
            if not task.get("owner_agent"):
                issues.append(f"active task {task['id']} has no owner_agent; start it with --agent or fix the board")
            if not task.get("scope"):
                issues.append(f"active task {task['id']} has no scope; set an honest scope or unlock it")
            owner = task.get("owner_agent") or ""
            agent = agents.get(owner)
            if owner and agent is None:
                issues.append(f"active task {task['id']} owner {owner} is not registered; run ai-board agents claim or fix agents")
            elif agent is not None and agent.get("task_id") not in ("", task["id"]):
                issues.append(f"agent {owner} points to {agent.get('task_id')} but active task is {task['id']}; release or reclaim the identity")
            elif agent is not None and agent_state(agent) == "expired":
                issues.append(f"agent {owner} lease is expired; run ai-board agents claim or ai-board renew {task['id']} --agent {owner}")

        conflicts = find_conflicts(board)
        if conflicts:
            for left, right, scope in conflicts:
                issues.append(f"scope conflict: {left['id']} and {right['id']} overlap on {scope}; coordinate, unlock, or narrow scope")
        else:
            print("scope conflicts: ok")

        expected_docs = {
            paths.current_board_doc: render_current_board(board),
            paths.archive_doc: render_archive(board),
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
            print("generated docs: ok")

    try:
        events = read_events(root)
    except SystemExit as error:
        issues.append(f"event log: {error}; fix or move .ai-board/events.jsonl")
    else:
        print(f"event log: ok ({len(events)} events)")

    if issues:
        for issue in issues:
            print(f"issue: {issue}")
        return 1 if args.fail_on_issue else 0
    print("doctor: ok")
    return 0


def cmd_locks(args: argparse.Namespace) -> int:
    board = load_board(root_path(args))
    active = [task for task in board["tasks"] if task["status"] == "active" and task.get("scope")]
    if not active:
        print("no locks")
        return 0
    for task in active:
        owner = task.get("lock_owner") or task.get("owner_agent") or "unknown"
        locked_at = task.get("locked_at") or task.get("started_at") or ""
        lease = task.get("lease_expires_at") or "none"
        state = "expired" if lock_is_expired(task) else "active"
        scope = ", ".join(task.get("scope", []))
        print(f"{task['id']} {owner} lock={state} locked_at={locked_at} lease_expires_at={lease} scope={scope}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    board = load_board(root_path(args))
    render_docs(root_path(args), board)
    print("rendered docs")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    board = load_board(root_path(args))
    task = find_task(board, args.task_id)
    print(json.dumps(task, ensure_ascii=False, indent=2))
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-board")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a board in the project.")
    init.add_argument("--project-name", default="", help="Project display name.")
    init.add_argument("--force", action="store_true", help="Overwrite existing board data.")
    init.add_argument("--overwrite-docs", action="store_true", help="Overwrite existing guardrail docs instead of writing .example files.")
    init.set_defaults(func=cmd_init)

    onboard = sub.add_parser("onboard", help="Inspect the project and print the AI-native handoff flow.")
    onboard.add_argument("--init-if-missing", action="store_true", help="Create the board and guardrail docs if they are missing.")
    onboard.add_argument("--project-name", default="", help="Project display name when --init-if-missing creates a board.")
    onboard.set_defaults(func=cmd_onboard)

    add = sub.add_parser("add", help="Add a task to inbox.")
    add.add_argument("title")
    add.add_argument("--priority", choices=PRIORITIES, default="P2")
    add.add_argument("--description", default="")
    add.add_argument("--lane", default="默认", help="Planning lane, for example platform, content, docs, or default.")
    add.add_argument("--source", default="", help="Where this task came from.")
    add.add_argument("--acceptance", action="append", default=[], help="Acceptance criterion. Can be passed multiple times.")
    add.add_argument("--depends-on", nargs="*", default=[], help="Task IDs this task depends on.")
    add.set_defaults(func=cmd_add)

    schedule = sub.add_parser("schedule", help="Move a task to scheduled work.")
    schedule.add_argument("task_id")
    schedule.set_defaults(func=cmd_schedule)

    start = sub.add_parser("start", help="Claim a scheduled task.")
    start.add_argument("task_id")
    start.add_argument("--agent", required=True)
    start.add_argument("--scope", nargs="*", default=[])
    start.add_argument("--force", action="store_true", help="Start even when scope overlaps an active task.")
    start.add_argument("--lease-minutes", type=int, default=DEFAULT_LEASE_MINUTES, help="Lock lease in minutes. Use 0 for no expiry.")
    start.set_defaults(func=cmd_start)

    renew = sub.add_parser("renew", help="Renew an active task scope lock.")
    renew.add_argument("task_id")
    renew.add_argument("--agent", required=True)
    renew.add_argument("--lease-minutes", type=int, default=DEFAULT_LEASE_MINUTES, help="New lock lease in minutes. Use 0 for no expiry.")
    renew.set_defaults(func=cmd_renew)

    unlock = sub.add_parser("unlock", help="Release an active task scope lock without completing the task.")
    unlock.add_argument("task_id")
    unlock.add_argument("--agent", required=True)
    unlock.add_argument("--force", action="store_true", help="Unlock even when another agent owns the lock.")
    unlock.set_defaults(func=cmd_unlock)

    agents = sub.add_parser("agents", help="Manage reusable agent identities.")
    agents_sub = agents.add_subparsers(dest="agents_command", required=True)

    agents_claim = agents_sub.add_parser("claim", help="Claim an idle agent identity, creating one if needed.")
    agents_claim.add_argument("--kind", default="agent", help="Agent family, for example codex or claude.")
    agents_claim.add_argument("--lease-minutes", type=int, default=DEFAULT_LEASE_MINUTES, help="Identity lease in minutes. Use 0 for no expiry.")
    agents_claim.set_defaults(func=cmd_agents_claim)

    agents_list = agents_sub.add_parser("list", help="List registered agent identities.")
    agents_list.set_defaults(func=cmd_agents_list)

    agents_release = agents_sub.add_parser("release", help="Release an idle or expired agent identity.")
    agents_release.add_argument("agent_id")
    agents_release.add_argument("--force", action="store_true", help="Release even when the identity is attached to an active task.")
    agents_release.set_defaults(func=cmd_agents_release)

    complete = sub.add_parser("complete", help="Complete an active task with verification.")
    complete.add_argument("task_id")
    complete.add_argument("--verification", required=True)
    complete.add_argument("--leftovers", default="")
    complete.set_defaults(func=cmd_complete)

    archive = sub.add_parser("archive", help="Archive a done task.")
    archive.add_argument("task_id")
    archive.set_defaults(func=cmd_archive)

    block = sub.add_parser("block", help="Mark a task blocked.")
    block.add_argument("task_id")
    block.set_defaults(func=cmd_block)

    goal = sub.add_parser("goal", help="Set current project goal.")
    goal.add_argument("goal")
    goal.set_defaults(func=cmd_goal)

    status = sub.add_parser("status", help="Print status counts.")
    status.set_defaults(func=cmd_status)

    conflicts = sub.add_parser("conflicts", help="Check active task scope conflicts.")
    conflicts.add_argument("--fail-on-conflict", action="store_true")
    conflicts.set_defaults(func=cmd_conflicts)

    doctor = sub.add_parser("doctor", help="Check project health.")
    doctor.add_argument("--fail-on-issue", action="store_true", help="Return non-zero when an issue is found.")
    doctor.set_defaults(func=cmd_doctor)

    locks = sub.add_parser("locks", help="List active task scope locks.")
    locks.set_defaults(func=cmd_locks)

    render = sub.add_parser("render", help="Render Markdown docs.")
    render.set_defaults(func=cmd_render)

    show = sub.add_parser("show", help="Print one task as JSON.")
    show.add_argument("task_id")
    show.set_defaults(func=cmd_show)

    history = sub.add_parser("history", help="Print event history.")
    history.add_argument("task_id", nargs="?", default="", help="Optional task ID to filter by.")
    history.set_defaults(func=cmd_history)

    skills = sub.add_parser("skills", help="Read AI usage guides bundled with this CLI.")
    skills_sub = skills.add_subparsers(dest="skills_command", required=True)

    skills_list = skills_sub.add_parser("list", help="List bundled AI usage guides.")
    skills_list.set_defaults(func=cmd_skills_list)

    skills_get = skills_sub.add_parser("get", help="Print a bundled AI usage guide.")
    skills_get.add_argument("skill_name", choices=skill_names())
    skills_get.add_argument("--full", action="store_true", help="Include extended command reference.")
    skills_get.set_defaults(func=cmd_skills_get)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
