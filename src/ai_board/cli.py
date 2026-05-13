from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .guardrails import init_guardrail_docs
from .operations import add_task, archive_task, complete_task, find_conflicts, schedule_task, set_goal, set_status, start_task
from .render import render_docs
from .skill_guides import SKILLS, get_skill, skill_names
from .store import PRIORITIES, STATUSES, find_task, init_board, load_board


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def root_path(args: argparse.Namespace) -> Path:
    return Path(args.root).expanduser().resolve()


def print_task(task: dict[str, Any]) -> None:
    print(f"{task['id']} [{task['status']}] {task.get('priority', 'P2')} {task['title']}")


def cmd_init(args: argparse.Namespace) -> int:
    board = init_board(root_path(args), args.project_name, args.force)
    written_docs = init_guardrail_docs(root_path(args), args.overwrite_docs)
    render_docs(root_path(args), board)
    print(f"initialized: {root_path(args)}")
    print(f"guardrail docs: {len(written_docs)}")
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
    task = start_task(root_path(args), args.task_id, args.agent, args.scope, args.force)
    print_task(task)
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
        scope = ", ".join(task.get("scope", []))
        print(f"{task['id']} {owner} locked_at={locked_at} lease_expires_at={lease} scope={scope}")
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
    start.set_defaults(func=cmd_start)

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

    locks = sub.add_parser("locks", help="List active task scope locks.")
    locks.set_defaults(func=cmd_locks)

    render = sub.add_parser("render", help="Render Markdown docs.")
    render.set_defaults(func=cmd_render)

    show = sub.add_parser("show", help="Print one task as JSON.")
    show.add_argument("task_id")
    show.set_defaults(func=cmd_show)

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
