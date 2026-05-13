from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BOARD_DIR = ".ai-board"
BOARD_FILE = "board.json"
DOCS_DIR = "docs"

STATUSES = ("inbox", "scheduled", "active", "done", "archived", "blocked")
PRIORITIES = ("P0", "P1", "P2", "P3")


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


def default_board() -> dict[str, Any]:
    created_at = now_iso()
    return {
        "schema_version": 1,
        "project": {"name": "", "current_goal": ""},
        "next_id": 1,
        "created_at": created_at,
        "updated_at": created_at,
        "tasks": [],
        "archive": [],
    }


def load_board(root: Path) -> dict[str, Any]:
    paths = Paths(root.resolve())
    if not paths.board_file.exists():
        raise SystemExit("Board not found. Run `ai-board init` first.")
    return json.loads(paths.board_file.read_text(encoding="utf-8"))


@contextmanager
def board_lock(root: Path, timeout: float = 10.0, poll_interval: float = 0.05):
    paths = Paths(root.resolve())
    paths.board_dir.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    handle = None
    while True:
        try:
            handle = os.open(paths.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(handle, f"pid={os.getpid()}\n".encode("utf-8"))
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise SystemExit(f"Board is locked: {paths.lock_file}")
            time.sleep(poll_interval)

    try:
        yield
    finally:
        if handle is not None:
            os.close(handle)
        try:
            paths.lock_file.unlink()
        except FileNotFoundError:
            pass


def save_board(root: Path, board: dict[str, Any]) -> None:
    paths = Paths(root.resolve())
    paths.board_dir.mkdir(parents=True, exist_ok=True)
    board["updated_at"] = now_iso()
    content = json.dumps(board, ensure_ascii=False, indent=2) + "\n"
    temp_file = paths.board_file.with_suffix(".json.tmp")
    temp_file.write_text(content, encoding="utf-8")
    temp_file.replace(paths.board_file)


def init_board(root: Path, project_name: str = "", force: bool = False) -> dict[str, Any]:
    paths = Paths(root.resolve())
    if paths.board_file.exists() and not force:
        return load_board(root)

    board = default_board()
    board["project"]["name"] = project_name or paths.root.name
    save_board(root, board)
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
    raise SystemExit(f"Task not found: {task_id}")


def active_tasks(board: dict[str, Any]) -> list[dict[str, Any]]:
    return [task for task in board["tasks"] if task["status"] == "active"]


def normalize_scope(paths: list[str]) -> list[str]:
    return sorted({path.strip().replace("\\", "/").strip("/") for path in paths if path.strip()})
