from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .datetime_utils import parse_iso_datetime
from .errors import BoardError, ScopeConflictError
from .render import render_docs
from .store import (
    PRIORITIES,
    STATUSES,
    VERIFICATION_KINDS,
    VERIFICATION_STATUSES,
    active_tasks,
    append_event,
    board_lock,
    find_task,
    find_verification,
    load_board,
    load_config,
    next_task_id,
    next_verification_id,
    normalize_scope,
    now_iso,
    save_board,
)

DEFAULT_LEASE_MINUTES = 240
DEFAULT_AGENT_KIND = "agent"
ALLOWED_STATUS_TRANSITIONS = {
    "inbox": {"scheduled", "blocked"},
    "blocked": {"scheduled", "archived"},
    "scheduled": {"active", "blocked"},
    "active": {"done", "blocked"},
    "done": {"archived"},
    "archived": set(),
}


def persist(root: Path, board: dict[str, Any]) -> dict[str, Any]:
    save_board(root, board)
    render_docs(root, board)
    return board


def record_event(root: Path, action: str, task: dict[str, Any] | None = None, agent: str = "", data: dict[str, Any] | None = None) -> None:
    append_event(root, action, task.get("id", "") if task else "", agent or (task or {}).get("owner_agent", ""), data)


def verification_event_action(verification: dict[str, Any]) -> str:
    if verification.get("status") == "failed":
        return "verification.failed"
    if verification.get("kind") == "deferred" or verification.get("status") == "deferred":
        return "verification.deferred"
    return "verification.recorded"


def record_verification_evidence(
    root: Path,
    task_id: str,
    kind: str,
    status: str,
    agent: str = "",
    command: str = "",
    exit_code: int | None = None,
    summary: str = "",
    output_excerpt: str = "",
    scope: list[str] | None = None,
    evidence_path: str = "",
) -> dict[str, Any]:
    if kind not in VERIFICATION_KINDS:
        raise BoardError(f"Invalid verification kind: {kind}. Use one of {', '.join(VERIFICATION_KINDS)}.")
    if status not in VERIFICATION_STATUSES:
        raise BoardError(f"Invalid verification status: {status}. Use one of {', '.join(VERIFICATION_STATUSES)}.")
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        verification = {
            "id": next_verification_id(board),
            "task_id": task["id"],
            "kind": kind,
            "status": status,
            "agent": agent,
            "command": command,
            "exit_code": exit_code,
            "summary": summary,
            "output_excerpt": output_excerpt,
            "scope": normalize_scope(scope or []),
            "evidence_path": evidence_path,
            "created_at": now_iso(),
        }
        board.setdefault("verifications", []).append(verification)
        persist(root, board)
        record_event(
            root,
            verification_event_action(verification),
            task,
            agent,
            {
                "verification_id": verification["id"],
                "kind": kind,
                "status": status,
                "exit_code": exit_code,
                "scope": verification["scope"],
            },
        )
        return verification


def ensure_agents(board: dict[str, Any]) -> list[dict[str, Any]]:
    return board.setdefault("agents", [])


def normalize_agent_kind(kind: str) -> str:
    normalized = kind.strip().lower().replace(" ", "-")
    if not normalized:
        raise BoardError("Agent kind is required.")
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


def ensure_scope_arguments_are_unambiguous(root: Path, scope: list[str]) -> None:
    for item in scope:
        raw = item.strip()
        if " " not in raw:
            continue
        if (root / raw).exists():
            continue
        raise BoardError(
            "Scope path contains spaces and does not exist: "
            f"{raw}. If you meant multiple paths, pass each path as a separate "
            "--scope argument; if this is one path with spaces, create it first "
            "or check the spelling."
        )


def claim_agent(root: Path, kind: str, lease_minutes: int = DEFAULT_LEASE_MINUTES) -> dict[str, Any]:
    if not kind:
        kind = str(load_config(root)["default_agent_kind"])
    normalized_kind = normalize_agent_kind(kind)
    if lease_minutes < 0:
        lease_minutes = int(load_config(root)["default_lease_minutes"])
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
        record_event(root, "agents.claim", agent=agent["id"], data={"kind": normalized_kind, "lease_expires_at": agent.get("lease_expires_at", "")})
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
            raise BoardError(f"Agent not found: {agent_id}")
        task_id = agent.get("task_id") or ""
        if task_id and not force:
            task = find_task(board, task_id)
            if task.get("status") == "active":
                raise BoardError(f"Agent is busy on active task {task_id}. Complete/archive the task or use --force.")
        release_agent_record(agent)
        persist(root, board)
        record_event(root, "agents.release", agent=agent_id, data={"previous_task_id": task_id, "force": force})
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
        raise BoardError(f"Agent {agent_id} is busy on {current_task_id}. Claim an idle identity first.")
    reserve_agent(agent, lease_minutes, task_id)
    return agent


def release_task_agent(board: dict[str, Any], task: dict[str, Any]) -> None:
    agent_id = task.get("owner_agent") or ""
    if not agent_id:
        return
    agent = find_agent(board, agent_id)
    if agent is not None and agent.get("task_id") == task.get("id"):
        release_agent_record(agent)


def ensure_status_transition(task: dict[str, Any], target_status: str) -> None:
    if target_status not in STATUSES:
        raise BoardError(f"Invalid status: {target_status}. Use one of {', '.join(STATUSES)}.")
    current_status = task.get("status", "")
    if target_status not in ALLOWED_STATUS_TRANSITIONS.get(current_status, set()):
        raise BoardError(f"Cannot move task {task.get('id', '')} from {current_status} to {target_status}.")


def transition_task(task: dict[str, Any], target_status: str) -> None:
    ensure_status_transition(task, target_status)
    task["status"] = target_status
    task["updated_at"] = now_iso()


def normalize_task_id(task_id: str) -> str:
    normalized = task_id.strip().upper()
    if not normalized:
        raise BoardError("Dependency task ID cannot be empty.")
    return normalized


def normalize_dependency_ids(depends_on: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for task_id in depends_on:
        item = normalize_task_id(task_id)
        if item not in seen:
            normalized.append(item)
            seen.add(item)
    return normalized


def all_task_ids(board: dict[str, Any]) -> set[str]:
    return {task["id"].upper() for task in board["tasks"] + board["archive"]}


def preview_next_task_id(board: dict[str, Any]) -> str:
    return f"T-{int(board.get('next_id', 1)):04d}"


def validate_task_dependencies(board: dict[str, Any], task_id: str, depends_on: list[str]) -> None:
    normalized_task_id = task_id.upper()
    if normalized_task_id in depends_on:
        raise BoardError(f"Task {task_id} cannot depend on itself.")
    missing = [dependency for dependency in depends_on if dependency not in all_task_ids(board)]
    if missing:
        raise BoardError(f"Unknown dependency task(s): {', '.join(missing)}")
    if has_dependency_cycle(board, normalized_task_id, depends_on):
        raise BoardError(f"Dependency cycle detected for {task_id}.")


def has_dependency_cycle(board: dict[str, Any], task_id: str, depends_on: list[str]) -> bool:
    graph = {task["id"].upper(): normalize_dependency_ids(task.get("depends_on", [])) for task in board["tasks"] + board["archive"]}
    graph[task_id] = depends_on
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(current: str) -> bool:
        if current in visiting:
            return True
        if current in visited:
            return False
        visiting.add(current)
        for dependency in graph.get(current, []):
            if visit(dependency):
                return True
        visiting.remove(current)
        visited.add(current)
        return False

    return visit(task_id)


def ensure_dependencies_complete(board: dict[str, Any], task: dict[str, Any], force: bool = False) -> None:
    depends_on = normalize_dependency_ids(task.get("depends_on", []))
    validate_task_dependencies(board, task["id"], depends_on)
    task["depends_on"] = depends_on
    if force:
        return
    unfinished: list[str] = []
    for dependency_id in depends_on:
        dependency = find_task(board, dependency_id)
        if dependency.get("status") not in ("done", "archived"):
            unfinished.append(f"{dependency_id} [{dependency.get('status')}]")
    if unfinished:
        raise BoardError("Task dependencies are not complete: " + ", ".join(unfinished) + ". Use --force only after confirming this is intentional.")


def add_task(
    root: Path,
    title: str,
    priority: str,
    description: str = "",
    lane: str = "",
    source: str = "",
    acceptance: list[str] | None = None,
    depends_on: list[str] | None = None,
    verify_scope: list[str] | None = None,
) -> dict[str, Any]:
    if priority not in PRIORITIES:
        raise BoardError(f"Invalid priority: {priority}. Use one of {', '.join(PRIORITIES)}.")
    if not lane:
        lane = str(load_config(root)["default_lane"])
    with board_lock(root):
        board = load_board(root)
        dependency_ids = normalize_dependency_ids(depends_on or [])
        normalized_verify_scope = normalize_scope(verify_scope or [])
        validate_task_dependencies(board, preview_next_task_id(board), dependency_ids)
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
            "verify_scope": normalized_verify_scope,
            "depends_on": dependency_ids,
            "acceptance": acceptance or [],
            "verification": "",
            "deferred_verification": "",
            "leftovers": "",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        board["tasks"].append(task)
        persist(root, board)
        record_event(root, "task.add", task, data={"title": title, "priority": priority, "lane": task["lane"], "source": source, "verify_scope": normalized_verify_scope})
        return task


def set_goal(root: Path, goal: str) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        board.setdefault("project", {})["current_goal"] = goal
        persist(root, board)
        record_event(root, "goal.set", data={"goal": goal})
        return board


def set_status(root: Path, task_id: str, status: str) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        if task in board["archive"]:
            raise BoardError("Archived tasks cannot be changed.")
        previous_status = task["status"]
        transition_task(task, status)
        if previous_status == "active" and status == "blocked":
            task["lock_owner"] = ""
            task["lease_expires_at"] = ""
            release_task_agent(board, task)
        persist(root, board)
        action = "task.block" if status == "blocked" else f"task.{status}"
        record_event(root, action, task, data={"status": status})
        return task


def schedule_task(root: Path, task_id: str) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        dependency_ids = normalize_dependency_ids(task.get("depends_on", []))
        validate_task_dependencies(board, task["id"], dependency_ids)
        task["depends_on"] = dependency_ids
        transition_task(task, "scheduled")
        persist(root, board)
        record_event(root, "task.schedule", task, data={"status": "scheduled"})
        return task


def start_task(root: Path, task_id: str, agent: str, scope: list[str], force: bool = False, lease_minutes: int = DEFAULT_LEASE_MINUTES, enforce_scope_conflicts: bool = True) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        ensure_status_transition(task, "active")
        ensure_scope_arguments_are_unambiguous(root, scope)
        task_scope = normalize_scope(scope)
        if not task_scope:
            raise BoardError("Task scope is required. Start with specific files or small subdirectories, for example --scope src/app.py README.md.")
        ensure_dependencies_complete(board, task, force)
        conflicts = find_scope_conflicts(board, task, task_scope)
        if enforce_scope_conflicts and conflicts and not force:
            lines = [f"{left['id']} ({left.get('owner_agent')}) conflicts on {scope_text}" for left, scope_text in conflicts]
            raise ScopeConflictError("Scope is locked by active task(s):\n" + "\n".join(lines))
        assign_agent_to_task(board, agent, task_id, lease_minutes)
        transition_task(task, "active")
        task["owner_agent"] = agent
        task["scope"] = task_scope
        task["lock_owner"] = agent
        task["locked_at"] = now_iso()
        task["lease_expires_at"] = lease_expires_at(lease_minutes)
        task["started_at"] = now_iso()
        task["updated_at"] = now_iso()
        persist(root, board)
        record_event(
            root,
            "task.start",
            task,
            agent,
            {"status": "active", "scope": task_scope, "lease_expires_at": task["lease_expires_at"], "force": force, "enforce_scope_conflicts": enforce_scope_conflicts},
        )
        return task


def renew_task_lock(root: Path, task_id: str, agent: str, lease_minutes: int = DEFAULT_LEASE_MINUTES) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        if task["status"] != "active":
            raise BoardError("Only active tasks can renew locks.")
        owner = task.get("lock_owner") or task.get("owner_agent")
        if owner and owner != agent:
            raise BoardError(f"Task lock is owned by {owner}. Use the owning agent or unlock with --force.")
        task["lock_owner"] = agent
        task["lease_expires_at"] = lease_expires_at(lease_minutes)
        task["updated_at"] = now_iso()
        assigned_agent = find_agent(board, agent)
        if assigned_agent is not None and assigned_agent.get("task_id") in ("", task_id):
            reserve_agent(assigned_agent, lease_minutes, task_id)
        persist(root, board)
        record_event(root, "task.renew", task, agent, {"lease_expires_at": task["lease_expires_at"]})
        return task


def rescope_task(
    root: Path,
    task_id: str,
    agent: str,
    scope: list[str],
    verify_scope: list[str] | None = None,
    force: bool = False,
    lease_minutes: int = DEFAULT_LEASE_MINUTES,
    enforce_scope_conflicts: bool = True,
) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        if task["status"] != "active":
            raise BoardError("Only active tasks can be rescoped.")
        owner = task.get("lock_owner") or task.get("owner_agent")
        if owner and owner != agent and not force:
            raise BoardError(f"Task is owned by {owner}. Use the owning agent or rescope with --force.")
        ensure_scope_arguments_are_unambiguous(root, scope)
        task_scope = normalize_scope(scope)
        if not task_scope:
            raise BoardError("Task scope is required. Start with specific files or small subdirectories, for example --scope src/app.py README.md.")
        normalized_verify_scope: list[str] | None = None
        if verify_scope is not None:
            ensure_scope_arguments_are_unambiguous(root, verify_scope)
            normalized_verify_scope = normalize_scope(verify_scope)
        conflicts = find_scope_conflicts(board, task, task_scope)
        if enforce_scope_conflicts and conflicts and not force:
            lines = [f"{left['id']} ({left.get('owner_agent')}) conflicts on {scope_text}" for left, scope_text in conflicts]
            raise ScopeConflictError("Scope is locked by active task(s):\n" + "\n".join(lines))
        assign_agent_to_task(board, agent, task_id, lease_minutes)
        task["owner_agent"] = agent
        task["scope"] = task_scope
        if normalized_verify_scope is not None:
            task["verify_scope"] = normalized_verify_scope
        task["lock_owner"] = agent
        task["locked_at"] = now_iso()
        task["lease_expires_at"] = lease_expires_at(lease_minutes)
        task["updated_at"] = now_iso()
        persist(root, board)
        event_data: dict[str, Any] = {
            "scope": task_scope,
            "lease_expires_at": task["lease_expires_at"],
            "force": force,
            "enforce_scope_conflicts": enforce_scope_conflicts,
        }
        if normalized_verify_scope is not None:
            event_data["verify_scope"] = normalized_verify_scope
        record_event(root, "task.rescope", task, agent, event_data)
        return task


def unlock_task(root: Path, task_id: str, agent: str, force: bool = False) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        if task["status"] != "active":
            raise BoardError("Only active tasks can be unlocked.")
        owner = task.get("lock_owner") or task.get("owner_agent")
        if owner and owner != agent and not force:
            raise BoardError(f"Task lock is owned by {owner}. Use --force to unlock it anyway.")
        task["lock_owner"] = ""
        task["lease_expires_at"] = ""
        task["unlocked_at"] = now_iso()
        task["updated_at"] = now_iso()
        persist(root, board)
        record_event(root, "task.unlock", task, agent, {"force": force, "scope": task.get("scope", [])})
        return task


def complete_task(
    root: Path,
    task_id: str,
    verification: str = "",
    leftovers: str = "",
    deferred_verification: str = "",
    verification_ids: list[str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        normalized_verification_ids = [item.upper() for item in verification_ids or []]
        linked_verifications = [find_verification(board, item) for item in normalized_verification_ids]
        for linked in linked_verifications:
            if str(linked.get("task_id", "")).upper() != task["id"].upper():
                raise BoardError(f"Verification {linked['id']} belongs to {linked.get('task_id')}, not {task['id']}.")
        non_passed = [linked for linked in linked_verifications if linked.get("status") != "passed"]
        if non_passed and not force:
            bad = ", ".join(f"{item['id']} [{item.get('status')}]" for item in non_passed)
            raise BoardError(f"Verification evidence is not passed: {bad}. Re-run verification or use --force with leftovers/deferred-verification.")
        if force and non_passed and not (leftovers.strip() or deferred_verification.strip()):
            raise BoardError("--force with non-passed verification evidence requires --leftovers or --deferred-verification.")
        if not verification.strip() and not normalized_verification_ids:
            raise BoardError("Verification is required.")
        if not verification.strip() and normalized_verification_ids:
            verification = "verification evidence: " + ", ".join(normalized_verification_ids)
        transition_task(task, "done")
        task["verification"] = verification
        task["verification_ids"] = normalized_verification_ids
        task["verification_force"] = bool(force and non_passed)
        task["deferred_verification"] = deferred_verification
        task["leftovers"] = leftovers
        task["lock_owner"] = ""
        task["lease_expires_at"] = ""
        task["completed_at"] = now_iso()
        task["updated_at"] = now_iso()
        release_task_agent(board, task)
        persist(root, board)
        record_event(
            root,
            "task.complete",
            task,
            data={
                "status": "done",
                "verification": verification,
                "verification_ids": normalized_verification_ids,
                "verification_force": task["verification_force"],
                "deferred_verification": deferred_verification,
                "leftovers": leftovers,
            },
        )
        return task


def archive_task(root: Path, task_id: str) -> dict[str, Any]:
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        transition_task(task, "archived")
        board["tasks"] = [item for item in board["tasks"] if item["id"] != task["id"]]
        task["archived_at"] = now_iso()
        task["updated_at"] = now_iso()
        board["archive"].append(task)
        release_task_agent(board, task)
        persist(root, board)
        record_event(root, "task.archive", task, data={"status": "archived"})
        return task


def reopen_task(root: Path, task_id: str, reason: str) -> dict[str, Any]:
    if not reason.strip():
        raise BoardError("Reopen reason is required.")
    with board_lock(root):
        board = load_board(root)
        task = find_task(board, task_id)
        previous_status = task["status"]
        if previous_status not in ("blocked", "done", "archived"):
            raise BoardError(f"Cannot reopen task {task['id']} from {previous_status}. Only blocked, done, or archived tasks can be reopened.")
        if task in board["archive"]:
            board["archive"] = [item for item in board["archive"] if item["id"] != task["id"]]
            board["tasks"].append(task)
        task["status"] = "scheduled"
        task["reopened_at"] = now_iso()
        task["reopen_reason"] = reason
        task["updated_at"] = now_iso()
        persist(root, board)
        record_event(root, "task.reopen", task, data={"from_status": previous_status, "status": "scheduled", "reason": reason})
        return task


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
        if task.get("scope") and task.get("lock_owner") and (include_expired or not lock_is_expired(task))
    ]


def scopes_overlap(left: str, right: str) -> bool:
    if left == right:
        return True
    if left == "." or right == ".":
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
