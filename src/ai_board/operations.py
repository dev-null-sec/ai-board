from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .render import render_docs
from .store import PRIORITIES, STATUSES, active_tasks, board_lock, find_task, load_board, next_task_id, normalize_scope, now_iso, save_board

DEFAULT_LEASE_MINUTES = 240
DEFAULT_AGENT_KIND = "agent"


def persist(root: Path, board: dict[str, Any]) -> dict[str, Any]:
    save_board(root, board)
    render_docs(root, board)
    return board


def ensure_agents(board: dict[str, Any]) -> list[dict[str, Any]]:
    return board.setdefault("agents", [])


def normalize_agent_kind(kind: str) -> str:
    normalized = kind.strip().lower().replace(" ", "-")
    if not normalized:
        raise SystemExit("Agent kind is required.")
    return normalized


def agent_kind_from_id(agent_id: str) -> str:
    if "-" in agent_id:
        prefix, suffix = agent_id.rsplit("-", 1)
        if prefix and suffix.isdigit():
            return normalize_agent_kind(prefix)
    return normalize_agent_kind(agent_id or DEFAULT_AGENT_KIND)


def find_agent(board: dict[str, Any], agent_id: str) -> dict[str, Any] | None:
    for agent in ensure_agents(board):
        if agent.get("id") == agent_id:
            return agent
    return None


def agent_is_expired(agent: dict[str, Any], now: datetime | None = None) -> bool:
    expires_at = parse_iso_datetime(agent.get("lease_expires_at", ""))
    if expires_at is None:
        return False
    return expires_at <= (now or datetime.now(timezone.utc))


def agent_state(agent: dict[str, Any]) -> str:
    if agent.get("status") == "busy" and agent_is_expired(agent):
        return "expired"
    return agent.get("status") or "idle"


def next_agent_id(board: dict[str, Any], kind: str) -> str:
    prefix = f"{kind}-"
    used_numbers: list[int] = []
    for agent in ensure_agents(board):
        agent_id = agent.get("id", "")
        if agent_id.startswith(prefix):
            suffix = agent_id.removeprefix(prefix)
            if suffix.isdigit():
                used_numbers.append(int(suffix))
    next_number = max(used_numbers, default=-1) + 1
    return f"{kind}-{next_number:02d}"


def reserve_agent(agent: dict[str, Any], lease_minutes: int, task_id: str = "") -> dict[str, Any]:
    agent["status"] = "busy"
    agent["task_id"] = task_id
    agent["lease_expires_at"] = lease_expires_at(lease_minutes)
    agent["claimed_at"] = agent.get("claimed_at") or now_iso()
    agent["updated_at"] = now_iso()
    return agent


def release_agent_record(agent: dict[str, Any]) -> None:
    agent["status"] = "idle"
    agent["task_id"] = ""
    agent["lease_expires_at"] = ""
    agent["released_at"] = now_iso()
    agent["updated_at"] = now_iso()


def claim_agent(root: Path, kind: str, lease_minutes: int = DEFAULT_LEASE_MINUTES) -> dict[str, Any]:
    normalized_kind = normalize_agent_kind(kind)
    with board_lock(root):
        board = load_board(root)
        agents = ensure_agents(board)
        reusable = [
            agent
            for agent in agents
            if agent.get("kind") == normalized_kind and agent_state(agent) in ("idle", "expired")
        ]
        agent = reusable[0] if reusable else None
        if agent is None:
            agent = {
                "id": next_agent_id(board, normalized_kind),
                "kind": normalized_kind,
                "status": "idle",
                "task_id": "",
                "lease_expires_at": "",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            agents.append(agent)
        reserve_agent(agent, lease_minutes)
        persist(root, board)
        return agent


def list_agents(root: Path) -> list[dict[str, Any]]:
    board = load_board(root)
    agents: list[dict[str, Any]] = []
    for agent in ensure_agents(board):
        item = dict(agent)
        item["state"] = agent_state(agent)
        agents.append(item)
    return agents


def release_agent(root: Path, agent_id: str, force: bool = False) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        agent = find_agent(board, agent_id)
        if agent is None:
            raise SystemExit(f"Agent not found: {agent_id}")
        task_id = agent.get("task_id") or ""
        if task_id and not force:
            task = find_task(board, task_id)
            if task.get("status") == "active":
                raise SystemExit(f"Agent is busy on active task {task_id}. Complete/archive the task or use --force.")
        release_agent_record(agent)
        persist(root, board)
        return agent


def assign_agent_to_task(board: dict[str, Any], agent_id: str, task_id: str, lease_minutes: int) -> dict[str, Any]:
    agent = find_agent(board, agent_id)
    if agent is None:
        agent = {
            "id": agent_id,
            "kind": agent_kind_from_id(agent_id),
            "status": "idle",
            "task_id": "",
            "lease_expires_at": "",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        ensure_agents(board).append(agent)
    state = agent_state(agent)
    current_task_id = agent.get("task_id") or ""
    if state == "busy" and current_task_id and current_task_id != task_id:
        raise SystemExit(f"Agent {agent_id} is busy on {current_task_id}. Claim an idle identity first.")
    reserve_agent(agent, lease_minutes, task_id)
    return agent


def release_task_agent(board: dict[str, Any], task: dict[str, Any]) -> None:
    agent_id = task.get("owner_agent") or ""
    if not agent_id:
        return
    agent = find_agent(board, agent_id)
    if agent is not None and agent.get("task_id") == task.get("id"):
        release_agent_record(agent)


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


def start_task(root: Path, task_id: str, agent: str, scope: list[str], force: bool = False, lease_minutes: int = DEFAULT_LEASE_MINUTES) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        if task["status"] != "scheduled":
            raise SystemExit("Only scheduled tasks can be started.")
        task_scope = normalize_scope(scope)
        assign_agent_to_task(board, agent, task_id, lease_minutes)
        conflicts = find_scope_conflicts(board, task, task_scope)
        if conflicts and not force:
            lines = [f"{left['id']} ({left.get('owner_agent')}) conflicts on {scope_text}" for left, scope_text in conflicts]
            raise SystemExit("Scope is locked by active task(s):\n" + "\n".join(lines))
        task["status"] = "active"
        task["owner_agent"] = agent
        task["scope"] = task_scope
        task["lock_owner"] = agent
        task["locked_at"] = now_iso()
        task["lease_expires_at"] = lease_expires_at(lease_minutes)
        task["started_at"] = now_iso()
        task["updated_at"] = now_iso()
        persist(root, board)
        return task


def renew_task_lock(root: Path, task_id: str, agent: str, lease_minutes: int = DEFAULT_LEASE_MINUTES) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        if task["status"] != "active":
            raise SystemExit("Only active tasks can renew locks.")
        owner = task.get("lock_owner") or task.get("owner_agent")
        if owner and owner != agent:
            raise SystemExit(f"Task lock is owned by {owner}. Use the owning agent or unlock with --force.")
        task["lock_owner"] = agent
        task["lease_expires_at"] = lease_expires_at(lease_minutes)
        task["updated_at"] = now_iso()
        assigned_agent = find_agent(board, agent)
        if assigned_agent is not None and assigned_agent.get("task_id") in ("", task_id):
            reserve_agent(assigned_agent, lease_minutes, task_id)
        persist(root, board)
        return task


def unlock_task(root: Path, task_id: str, agent: str, force: bool = False) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        if task["status"] != "active":
            raise SystemExit("Only active tasks can be unlocked.")
        owner = task.get("lock_owner") or task.get("owner_agent")
        if owner and owner != agent and not force:
            raise SystemExit(f"Task lock is owned by {owner}. Use --force to unlock it anyway.")
        task["scope"] = []
        task["lock_owner"] = ""
        task["lease_expires_at"] = ""
        task["unlocked_at"] = now_iso()
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
        release_task_agent(board, task)
        persist(root, board)
        return task


def parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def lease_expires_at(lease_minutes: int) -> str:
    if lease_minutes <= 0:
        return ""
    return (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=lease_minutes)).isoformat()


def lock_is_expired(task: dict[str, Any], now: datetime | None = None) -> bool:
    expires_at = parse_iso_datetime(task.get("lease_expires_at", ""))
    if expires_at is None:
        return False
    return expires_at <= (now or datetime.now(timezone.utc))


def locked_active_tasks(board: dict[str, Any], include_expired: bool = False) -> list[dict[str, Any]]:
    return [
        task
        for task in active_tasks(board)
        if task.get("scope") and (include_expired or not lock_is_expired(task))
    ]


def scopes_overlap(left: str, right: str) -> bool:
    if left == right:
        return True
    left_prefix = f"{left.rstrip('/')}/"
    right_prefix = f"{right.rstrip('/')}/"
    return left.startswith(right_prefix) or right.startswith(left_prefix)


def find_conflicts(board: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any], str]]:
    conflicts: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    tasks = locked_active_tasks(board)
    for index, left in enumerate(tasks):
        for right in tasks[index + 1 :]:
            for left_scope in left.get("scope", []):
                for right_scope in right.get("scope", []):
                    if scopes_overlap(left_scope, right_scope):
                        conflicts.append((left, right, left_scope if left_scope == right_scope else f"{left_scope} <-> {right_scope}"))
    return conflicts


def find_scope_conflicts(board: dict[str, Any], candidate: dict[str, Any], candidate_scope: list[str]) -> list[tuple[dict[str, Any], str]]:
    conflicts: list[tuple[dict[str, Any], str]] = []
    for task in locked_active_tasks(board):
        if task["id"] == candidate["id"]:
            continue
        for locked_scope in task.get("scope", []):
            for scope in candidate_scope:
                if scopes_overlap(locked_scope, scope):
                    conflicts.append((task, locked_scope if locked_scope == scope else f"{locked_scope} <-> {scope}"))
    return conflicts
