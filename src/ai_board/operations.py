from __future__ import annotations

from pathlib import Path
from typing import Any

from .render import render_docs
from .store import PRIORITIES, STATUSES, active_tasks, board_lock, find_task, load_board, next_task_id, normalize_scope, now_iso, save_board


def persist(root: Path, board: dict[str, Any]) -> dict[str, Any]:
    save_board(root, board)
    render_docs(root, board)
    return board


def add_task(
    root: Path,
    title: str,
    priority: str,
    description: str = "",
    lane: str = "",
    source: str = "",
    acceptance: list[str] | None = None,
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    if priority not in PRIORITIES:
        raise SystemExit(f"Invalid priority: {priority}. Use one of {', '.join(PRIORITIES)}.")
    with board_lock(root):
        board = load_board(root)
        task = {
            "id": next_task_id(board),
            "title": title,
            "description": description,
            "priority": priority,
            "status": "inbox",
            "lane": lane.strip() or "默认",
            "source": source,
            "owner_agent": "",
            "scope": [],
            "depends_on": depends_on or [],
            "acceptance": acceptance or [],
            "verification": "",
            "leftovers": "",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        board["tasks"].append(task)
        persist(root, board)
        return task


def set_goal(root: Path, goal: str) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        board.setdefault("project", {})["current_goal"] = goal
        persist(root, board)
        return board


def set_status(root: Path, task_id: str, status: str) -> dict[str, Any]:
    if status not in STATUSES:
        raise SystemExit(f"Invalid status: {status}. Use one of {', '.join(STATUSES)}.")
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        if task in board["archive"]:
            raise SystemExit("Archived tasks cannot be changed.")
        task["status"] = status
        task["updated_at"] = now_iso()
        persist(root, board)
        return task


def schedule_task(root: Path, task_id: str) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        if task["status"] not in ("inbox", "blocked"):
            raise SystemExit("Only inbox or blocked tasks can be scheduled.")
        task["status"] = "scheduled"
        task["updated_at"] = now_iso()
        persist(root, board)
        return task


def start_task(root: Path, task_id: str, agent: str, scope: list[str], force: bool = False) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        if task["status"] != "scheduled":
            raise SystemExit("Only scheduled tasks can be started.")
        task_scope = normalize_scope(scope)
        conflicts = find_scope_conflicts(board, task, task_scope)
        if conflicts and not force:
            lines = [f"{left['id']} ({left.get('owner_agent')}) conflicts on {scope_text}" for left, scope_text in conflicts]
            raise SystemExit("Scope is locked by active task(s):\n" + "\n".join(lines))
        task["status"] = "active"
        task["owner_agent"] = agent
        task["scope"] = task_scope
        task["lock_owner"] = agent
        task["locked_at"] = now_iso()
        task["lease_expires_at"] = ""
        task["started_at"] = now_iso()
        task["updated_at"] = now_iso()
        persist(root, board)
        return task


def complete_task(root: Path, task_id: str, verification: str, leftovers: str = "") -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        if task["status"] != "active":
            raise SystemExit("Only active tasks can be completed.")
        if not verification.strip():
            raise SystemExit("Verification is required.")
        task["status"] = "done"
        task["verification"] = verification
        task["leftovers"] = leftovers
        task["lock_owner"] = ""
        task["lease_expires_at"] = ""
        task["completed_at"] = now_iso()
        task["updated_at"] = now_iso()
        persist(root, board)
        return task


def archive_task(root: Path, task_id: str) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        if task["status"] != "done":
            raise SystemExit("Only done tasks can be archived.")
        board["tasks"] = [item for item in board["tasks"] if item["id"] != task["id"]]
        task["status"] = "archived"
        task["archived_at"] = now_iso()
        task["updated_at"] = now_iso()
        board["archive"].append(task)
        persist(root, board)
        return task


def scopes_overlap(left: str, right: str) -> bool:
    if left == right:
        return True
    left_prefix = f"{left.rstrip('/')}/"
    right_prefix = f"{right.rstrip('/')}/"
    return left.startswith(right_prefix) or right.startswith(left_prefix)


def find_conflicts(board: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any], str]]:
    conflicts: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    tasks = active_tasks(board)
    for index, left in enumerate(tasks):
        for right in tasks[index + 1 :]:
            for left_scope in left.get("scope", []):
                for right_scope in right.get("scope", []):
                    if scopes_overlap(left_scope, right_scope):
                        conflicts.append((left, right, left_scope if left_scope == right_scope else f"{left_scope} <-> {right_scope}"))
    return conflicts


def find_scope_conflicts(board: dict[str, Any], candidate: dict[str, Any], candidate_scope: list[str]) -> list[tuple[dict[str, Any], str]]:
    conflicts: list[tuple[dict[str, Any], str]] = []
    for task in active_tasks(board):
        if task["id"] == candidate["id"]:
            continue
        for locked_scope in task.get("scope", []):
            for scope in candidate_scope:
                if scopes_overlap(locked_scope, scope):
                    conflicts.append((task, locked_scope if locked_scope == scope else f"{locked_scope} <-> {scope}"))
    return conflicts
