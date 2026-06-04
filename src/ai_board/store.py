from __future__ import annotations

import json
import os
import re
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .datetime_utils import parse_iso_datetime
from .errors import BoardError, BoardLockError, BoardSchemaError, TaskNotFoundError

BOARD_DIR = ".ai-board"
BOARD_FILE = "board.json"
EVENTS_FILE = "events.jsonl"
FAILED_EVENTS_FILE = "events.failed.jsonl"
CONFIG_FILE = "config.json"
MESSAGES_FILE = "messages.jsonl"
DOCS_DIR = "docs"

STATUSES = ("inbox", "scheduled", "active", "done", "archived", "blocked")
PRIORITIES = ("P0", "P1", "P2", "P3")
BOARD_LOCK_STALE_SECONDS = 30 * 60
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def board_dir(self) -> Path:
        return self.root / BOARD_DIR

    @property
    def board_file(self) -> Path:
        return self.board_dir / BOARD_FILE

    @property
    def lock_file(self) -> Path:
        return self.board_dir / "board.lock"

    @property
    def events_file(self) -> Path:
        return self.board_dir / EVENTS_FILE

    @property
    def failed_events_file(self) -> Path:
        return self.board_dir / FAILED_EVENTS_FILE

    @property
    def config_file(self) -> Path:
        return self.board_dir / CONFIG_FILE

    @property
    def messages_file(self) -> Path:
        return self.board_dir / MESSAGES_FILE

    @property
    def docs_dir(self) -> Path:
        return self.root / DOCS_DIR

    @property
    def current_board_doc(self) -> Path:
        return self.docs_dir / "计划看板.md"

    @property
    def archive_doc(self) -> Path:
        return self.docs_dir / "归档计划看板.md"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def next_message_id(messages: list[dict[str, Any]]) -> str:
    max_id = 0
    for message in messages:
        value = str(message.get("id", ""))
        if not value.startswith("M-"):
            continue
        try:
            max_id = max(max_id, int(value.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"M-{max_id + 1:04d}"


def default_board() -> dict[str, Any]:
    created_at = now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {"name": "", "current_goal": ""},
        "next_id": 1,
        "created_at": created_at,
        "updated_at": created_at,
        "agents": [],
        "tasks": [],
        "archive": [],
    }


def default_config() -> dict[str, Any]:
    return {
        "language": "zh-CN",
        "multi_agent_enabled": False,
        "git_integration": "suggest",
        "scope_gate": "suggest",
        "default_lane": "默认",
        "default_agent_kind": "agent",
        "default_lease_minutes": 240,
        "doctor_stale_active_hours": 48,
        "doctor_lease_warning_minutes": 30,
        "doctor_broad_scopes": [".", "src", "docs", "tests"],
        "shared_verification_scopes": ["tests", "tests/test_cli.py", "src/ai_board/cli.py", "src/ai_board/operations.py"],
        "shared_scope_warning_minutes": 30,
    }


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    if config["language"] not in ("zh-CN", "en-US"):
        raise BoardSchemaError("Config file is invalid: language must be zh-CN or en-US.")
    if not isinstance(config["multi_agent_enabled"], bool):
        raise BoardSchemaError("Config file is invalid: multi_agent_enabled must be true or false.")
    if config["git_integration"] not in ("suggest", "required", "off"):
        raise BoardSchemaError("Config file is invalid: git_integration must be suggest, required, or off.")
    if config["scope_gate"] not in ("suggest", "required", "off"):
        raise BoardSchemaError("Config file is invalid: scope_gate must be suggest, required, or off.")
    if not isinstance(config["default_lane"], str) or not config["default_lane"].strip():
        raise BoardSchemaError("Config file is invalid: default_lane must be a non-empty string.")
    if not isinstance(config["default_agent_kind"], str) or not config["default_agent_kind"].strip():
        raise BoardSchemaError("Config file is invalid: default_agent_kind must be a non-empty string.")
    try:
        config["default_lease_minutes"] = int(config["default_lease_minutes"])
    except (TypeError, ValueError) as error:
        raise BoardSchemaError("Config file is invalid: default_lease_minutes must be a number.") from error
    try:
        config["doctor_stale_active_hours"] = int(config["doctor_stale_active_hours"])
        config["doctor_lease_warning_minutes"] = int(config["doctor_lease_warning_minutes"])
        config["shared_scope_warning_minutes"] = int(config["shared_scope_warning_minutes"])
    except (TypeError, ValueError) as error:
        raise BoardSchemaError("Config file is invalid: doctor thresholds must be numbers.") from error
    if not isinstance(config["doctor_broad_scopes"], list) or any(not isinstance(item, str) for item in config["doctor_broad_scopes"]):
        raise BoardSchemaError("Config file is invalid: doctor_broad_scopes must be a list of strings.")
    if not isinstance(config["shared_verification_scopes"], list) or any(not isinstance(item, str) for item in config["shared_verification_scopes"]):
        raise BoardSchemaError("Config file is invalid: shared_verification_scopes must be a list of strings.")
    return config


def load_config(root: Path) -> dict[str, Any]:
    paths = Paths(root.resolve())
    config = default_config()
    if not paths.config_file.exists():
        return config
    try:
        loaded = json.loads(paths.config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise BoardSchemaError(f"Config file is not valid JSON: {paths.config_file} ({error.msg} at line {error.lineno}, column {error.colno})") from error
    except OSError as error:
        raise BoardError(f"Could not read config file: {paths.config_file} ({error})") from error
    if not isinstance(loaded, dict):
        raise BoardSchemaError("Config file is invalid: top-level value must be an object.")
    config.update({key: value for key, value in loaded.items() if key in config})
    return validate_config(config)


def save_config(root: Path, updates: dict[str, Any]) -> dict[str, Any]:
    paths = Paths(root.resolve())
    allowed_keys = set(default_config())
    unknown_keys = sorted(key for key in updates if key not in allowed_keys)
    if unknown_keys:
        raise BoardError(f"Unknown config key: {', '.join(unknown_keys)}")
    with board_lock(root):
        current = load_config(root)
        current.update(updates)
        current = validate_config(current)
        paths.board_dir.mkdir(parents=True, exist_ok=True)
        content = json.dumps(current, ensure_ascii=False, indent=2) + "\n"
        temp_file = paths.config_file.with_suffix(".json.tmp")
        temp_file.write_text(content, encoding="utf-8")
        temp_file.replace(paths.config_file)
        return current


def init_config(root: Path, force: bool = False) -> dict[str, Any]:
    paths = Paths(root.resolve())
    if paths.config_file.exists() and not force:
        return load_config(root)
    config = default_config()
    paths.board_dir.mkdir(parents=True, exist_ok=True)
    paths.config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return config


def load_board(root: Path) -> dict[str, Any]:
    paths = Paths(root.resolve())
    if not paths.board_file.exists():
        raise BoardError("Board not found. Run `ai-board init` first.")
    try:
        board = json.loads(paths.board_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise BoardSchemaError(f"Board file is not valid JSON: {paths.board_file} ({error.msg} at line {error.lineno}, column {error.colno})") from error
    except OSError as error:
        raise BoardError(f"Could not read board file: {paths.board_file} ({error})") from error
    return normalize_board(board)


def normalize_board(board: Any) -> dict[str, Any]:
    if not isinstance(board, dict):
        raise BoardSchemaError("Board file is invalid: top-level value must be an object.")
    version = board.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise BoardSchemaError(f"Unsupported board schema_version: {version}. Supported version: {SCHEMA_VERSION}.")

    changed_at = now_iso()
    board["schema_version"] = SCHEMA_VERSION
    project = board.setdefault("project", {})
    if not isinstance(project, dict):
        raise BoardSchemaError("Board file is invalid: project must be an object.")
    project.setdefault("name", "")
    project.setdefault("current_goal", "")

    try:
        board["next_id"] = int(board.get("next_id", 1))
    except (TypeError, ValueError) as error:
        raise BoardSchemaError("Board file is invalid: next_id must be a number.") from error
    board.setdefault("created_at", changed_at)
    board.setdefault("updated_at", changed_at)
    tasks = require_list(board, "tasks")
    archive = require_list(board, "archive")
    agents = require_list(board, "agents")
    for task in tasks:
        normalize_task(task, archived=False)
    for task in archive:
        normalize_task(task, archived=True)
    for agent in agents:
        normalize_agent(agent)
    return board


def require_list(board: dict[str, Any], key: str) -> list[Any]:
    value = board.setdefault(key, [])
    if not isinstance(value, list):
        raise BoardSchemaError(f"Board file is invalid: {key} must be a list.")
    return value


def normalize_task(task: Any, archived: bool) -> dict[str, Any]:
    if not isinstance(task, dict):
        raise BoardSchemaError("Board file is invalid: every task must be an object.")
    task_id = task.get("id")
    title = task.get("title")
    if not isinstance(task_id, str) or not task_id:
        raise BoardSchemaError("Board file is invalid: every task needs a non-empty string id.")
    if not isinstance(title, str) or not title:
        raise BoardSchemaError(f"Board file is invalid: task {task_id} needs a non-empty string title.")
    status = task.get("status", "archived" if archived else "inbox")
    if status not in STATUSES:
        raise BoardSchemaError(f"Board file is invalid: task {task_id} has invalid status {status}.")
    task["status"] = status
    task.setdefault("description", "")
    task.setdefault("priority", "P2")
    if task["priority"] not in PRIORITIES:
        raise BoardSchemaError(f"Board file is invalid: task {task_id} has invalid priority {task['priority']}.")
    task.setdefault("lane", "默认")
    task.setdefault("source", "")
    task.setdefault("owner_agent", "")
    ensure_task_list(task, "scope", task_id)
    task["scope"] = normalize_scope(task["scope"])
    ensure_task_list(task, "verify_scope", task_id)
    task["verify_scope"] = normalize_scope(task["verify_scope"])
    ensure_task_list(task, "depends_on", task_id)
    ensure_task_list(task, "acceptance", task_id)
    task.setdefault("verification", "")
    task.setdefault("deferred_verification", "")
    task.setdefault("leftovers", "")
    task.setdefault("created_at", now_iso())
    task.setdefault("updated_at", task.get("created_at") or now_iso())
    task.setdefault("lock_owner", "")
    task.setdefault("lease_expires_at", "")
    return task


def ensure_task_list(task: dict[str, Any], key: str, task_id: str) -> None:
    value = task.setdefault(key, [])
    if not isinstance(value, list):
        raise BoardSchemaError(f"Board file is invalid: task {task_id} field {key} must be a list.")
    if any(not isinstance(item, str) for item in value):
        raise BoardSchemaError(f"Board file is invalid: task {task_id} field {key} must contain only strings.")


def normalize_agent(agent: Any) -> dict[str, Any]:
    if not isinstance(agent, dict):
        raise BoardSchemaError("Board file is invalid: every agent must be an object.")
    agent_id = agent.get("id")
    if not isinstance(agent_id, str) or not agent_id:
        raise BoardSchemaError("Board file is invalid: every agent needs a non-empty string id.")
    agent.setdefault("kind", agent_id.rsplit("-", 1)[0] if "-" in agent_id else agent_id)
    status = agent.get("status", "idle")
    if status not in ("idle", "busy"):
        raise BoardSchemaError(f"Board file is invalid: agent {agent_id} has invalid status {status}.")
    agent["status"] = status
    agent.setdefault("task_id", "")
    agent.setdefault("lease_expires_at", "")
    agent.setdefault("created_at", now_iso())
    agent.setdefault("updated_at", agent.get("created_at") or now_iso())
    return agent


def process_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def lock_metadata(command: str = "") -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "created_at": now_iso(),
        "command": command,
    }


def read_lock_metadata(lock_file: Path) -> dict[str, Any]:
    try:
        text = lock_file.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data: dict[str, Any] = {}
        for line in text.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
        return data
    return data if isinstance(data, dict) else {}


def lock_is_stale(lock_file: Path, stale_seconds: int = BOARD_LOCK_STALE_SECONDS) -> tuple[bool, str]:
    metadata = read_lock_metadata(lock_file)
    pid_value = metadata.get("pid")
    pid = int(pid_value) if str(pid_value or "").isdigit() else 0
    created_at = parse_iso_datetime(str(metadata.get("created_at") or ""))
    age_limit = datetime.now(timezone.utc) - timedelta(seconds=stale_seconds)
    if created_at is not None and created_at <= age_limit:
        return True, f"older than {stale_seconds} seconds"
    if pid and not process_is_running(pid):
        return True, f"pid {pid} is not running"
    return False, ""


def clear_stale_lock(lock_file: Path, stale_seconds: int = BOARD_LOCK_STALE_SECONDS) -> bool:
    if not lock_file.exists():
        return False
    stale, _reason = lock_is_stale(lock_file, stale_seconds)
    if not stale:
        return False
    try:
        lock_file.unlink()
    except FileNotFoundError:
        return False
    except PermissionError:
        return False
    return True


@contextmanager
def board_lock(root: Path, timeout: float = 10.0, poll_interval: float = 0.05, stale_seconds: int = BOARD_LOCK_STALE_SECONDS, command: str = ""):
    paths = Paths(root.resolve())
    paths.board_dir.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    handle = None
    while True:
        try:
            handle = os.open(paths.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            content = json.dumps(lock_metadata(command), ensure_ascii=False, indent=2) + "\n"
            os.write(handle, content.encode("utf-8"))
            break
        except FileExistsError as error:
            clear_stale_lock(paths.lock_file, stale_seconds)
            if not paths.lock_file.exists():
                continue
            if time.monotonic() >= deadline:
                metadata = read_lock_metadata(paths.lock_file)
                stale, reason = lock_is_stale(paths.lock_file, stale_seconds)
                detail = f" metadata={metadata}" if metadata else ""
                stale_text = f" stale={reason}" if stale else ""
                raise BoardLockError(f"Board is locked: {paths.lock_file}.{stale_text}{detail}") from error
            time.sleep(poll_interval)

    try:
        yield
    finally:
        if handle is not None:
            os.close(handle)
        deadline = time.monotonic() + 1.0
        while True:
            try:
                paths.lock_file.unlink()
                break
            except FileNotFoundError:
                break
            except PermissionError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(poll_interval)


def save_board(root: Path, board: dict[str, Any]) -> None:
    paths = Paths(root.resolve())
    paths.board_dir.mkdir(parents=True, exist_ok=True)
    board["updated_at"] = now_iso()
    content = json.dumps(board, ensure_ascii=False, indent=2) + "\n"
    temp_file = paths.board_file.with_suffix(".json.tmp")
    temp_file.write_text(content, encoding="utf-8")
    temp_file.replace(paths.board_file)


def append_event(root: Path, action: str, task_id: str = "", agent: str = "", data: dict[str, Any] | None = None) -> None:
    paths = Paths(root.resolve())
    event = {
        "created_at": now_iso(),
        "action": action,
        "task_id": task_id,
        "agent": agent,
        "data": data or {},
    }
    try:
        paths.board_dir.mkdir(parents=True, exist_ok=True)
        with paths.events_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError as error:
        print(f"warning: could not append event log: {paths.events_file} ({error})", file=sys.stderr)
        failed_event = {
            "created_at": now_iso(),
            "error": str(error),
            "event": event,
        }
        try:
            paths.board_dir.mkdir(parents=True, exist_ok=True)
            with paths.failed_events_file.open("a", encoding="utf-8") as file:
                file.write(json.dumps(failed_event, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError as fallback_error:
            print(f"warning: could not append failed event log: {paths.failed_events_file} ({fallback_error})", file=sys.stderr)


def read_events(root: Path, task_id: str = "") -> list[dict[str, Any]]:
    paths = Paths(root.resolve())
    if not paths.events_file.exists():
        return []
    events: list[dict[str, Any]] = []
    normalized_task_id = task_id.upper()
    try:
        lines = paths.events_file.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise BoardError(f"Could not read event log: {paths.events_file} ({error})") from error
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise BoardSchemaError(f"Event log is not valid JSONL: {paths.events_file} line {line_number} ({error.msg})") from error
        if not isinstance(event, dict):
            raise BoardSchemaError(f"Event log is invalid: {paths.events_file} line {line_number} must be an object.")
        if normalized_task_id and str(event.get("task_id", "")).upper() != normalized_task_id:
            continue
        events.append(event)
    return events


def read_messages(root: Path) -> list[dict[str, Any]]:
    paths = Paths(root.resolve())
    if not paths.messages_file.exists():
        return []
    messages: list[dict[str, Any]] = []
    try:
        lines = paths.messages_file.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise BoardError(f"Could not read message log: {paths.messages_file} ({error})") from error
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as error:
            raise BoardSchemaError(f"Message log is not valid JSONL: {paths.messages_file} line {line_number} ({error.msg})") from error
        if not isinstance(message, dict):
            raise BoardSchemaError(f"Message log is invalid: {paths.messages_file} line {line_number} must be an object.")
        messages.append(message)
    return messages


def write_messages(root: Path, messages: list[dict[str, Any]]) -> None:
    paths = Paths(root.resolve())
    paths.board_dir.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(message, ensure_ascii=False, sort_keys=True) + "\n" for message in messages)
    temp_file = paths.messages_file.with_suffix(".jsonl.tmp")
    temp_file.write_text(content, encoding="utf-8")
    temp_file.replace(paths.messages_file)


def append_message(root: Path, sender: str, recipient: str, message_type: str, task_id: str, message_text: str) -> dict[str, Any]:
    allowed_types = {"info", "wait", "release", "handoff", "request"}
    if not sender.strip():
        raise BoardError("Message sender is required.")
    if not recipient.strip():
        raise BoardError("Message recipient is required.")
    if recipient != "all" and not recipient.strip():
        raise BoardError("Message recipient is required.")
    if message_type not in allowed_types:
        raise BoardError(f"Invalid message type: {message_type}. Use one of {', '.join(sorted(allowed_types))}.")
    if not message_text.strip():
        raise BoardError("Message text is required.")
    with board_lock(root):
        messages = read_messages(root)
        message = {
            "id": next_message_id(messages),
            "from": sender.strip(),
            "to": recipient.strip(),
            "type": message_type,
            "task_id": task_id.strip(),
            "message": message_text.strip(),
            "created_at": now_iso(),
            "acknowledged_at": "",
            "resolved_at": "",
        }
        messages.append(message)
        write_messages(root, messages)
        append_event(root, "message.tell", task_id=message["task_id"], agent=message["from"], data={"message_id": message["id"], "to": message["to"], "type": message["type"]})
        return message


def messages_for_agent(root: Path, agent: str, include_resolved: bool = False) -> list[dict[str, Any]]:
    if not agent.strip():
        raise BoardError("Agent is required.")
    messages = read_messages(root)
    result = []
    for message in messages:
        if message.get("to") not in (agent, "all"):
            continue
        if not include_resolved and message.get("resolved_at"):
            continue
        result.append(message)
    return result


def update_message_status(root: Path, message_id: str, agent: str, resolve: bool = False) -> dict[str, Any]:
    if not agent.strip():
        raise BoardError("Agent is required.")
    with board_lock(root):
        messages = read_messages(root)
        for message in messages:
            if message.get("id") != message_id:
                continue
            if message.get("to") not in (agent, "all"):
                raise BoardError(f"Message {message_id} is not addressed to {agent}.")
            if not message.get("acknowledged_at"):
                message["acknowledged_at"] = now_iso()
            action = "message.ack"
            if resolve:
                message["resolved_at"] = now_iso()
                action = "message.resolve"
            write_messages(root, messages)
            append_event(root, action, task_id=str(message.get("task_id") or ""), agent=agent, data={"message_id": message_id})
            return message
    raise BoardError(f"Message not found: {message_id}")


def init_board(root: Path, project_name: str = "", force: bool = False) -> dict[str, Any]:
    paths = Paths(root.resolve())
    if paths.board_file.exists() and not force:
        return load_board(root)

    board = default_board()
    board["project"]["name"] = project_name or paths.root.name
    save_board(root, board)
    init_config(root)
    return board


def next_task_id(board: dict[str, Any]) -> str:
    value = int(board.get("next_id", 1))
    board["next_id"] = value + 1
    return f"T-{value:04d}"


def find_task(board: dict[str, Any], task_id: str) -> dict[str, Any]:
    normalized = task_id.upper()
    for task in board["tasks"]:
        if task["id"].upper() == normalized:
            return task
    for task in board["archive"]:
        if task["id"].upper() == normalized:
            return task
    raise TaskNotFoundError(f"Task not found: {task_id}")


def active_tasks(board: dict[str, Any]) -> list[dict[str, Any]]:
    return [task for task in board["tasks"] if task["status"] == "active"]


def normalize_scope(paths: list[str]) -> list[str]:
    normalized: set[str] = set()
    for path in paths:
        item = normalize_scope_path(path)
        if item:
            normalized.add(item)
    if "." in normalized:
        return ["."]
    return sorted(normalized)


def normalize_scope_path(path: str) -> str:
    raw = path.strip()
    if not raw:
        return ""
    value = raw.replace("\\", "/")
    if value.startswith("/") or re.match(r"^[A-Za-z]:($|/)", value):
        raise BoardError(f"Invalid scope path: {raw}. Scope must be relative to the project.")

    parts: list[str] = []
    for part in value.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise BoardError(f"Invalid scope path: {raw}. Scope cannot leave the project.")
            parts.pop()
            continue
        parts.append(part)
    return "/".join(parts) or "."
