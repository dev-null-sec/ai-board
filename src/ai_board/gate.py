from __future__ import annotations

import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import BoardError
from .operations import lock_is_expired, scopes_overlap
from .store import active_tasks, load_board, load_config, normalize_scope_path

BOOKKEEPING_PATHS = {
    ".ai-board/board.json",
    ".ai-board/config.json",
    ".ai-board/events.jsonl",
    ".ai-board/events.failed.jsonl",
    ".ai-board/messages.jsonl",
    "docs/计划看板.md",
    "docs/归档计划看板.md",
}


@dataclass(frozen=True)
class ScopeGateResult:
    mode: str
    checked_paths: list[str]
    ignored_paths: list[str]
    uncovered_paths: list[str]
    active_tasks: list[dict[str, Any]]

    @property
    def has_violations(self) -> bool:
        return bool(self.uncovered_paths)

    @property
    def exit_code(self) -> int:
        if self.mode == "required" and self.has_violations:
            return 1
        return 0


def parse_name_status(output: str) -> list[str]:
    paths: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        kind = status[:1]
        if kind in ("R", "C") and len(parts) >= 3:
            paths.extend([parts[1], parts[2]])
            continue
        if len(parts) >= 2:
            paths.append(parts[1])
    return paths


def read_staged_diff_paths(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "diff", "--cached", "--name-status"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError as error:
        raise BoardError("Git is not available. Install git before using scope gate.") from error
    except subprocess.TimeoutExpired as error:
        raise BoardError("Git staged diff timed out.") from error
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise BoardError(f"Could not read staged git diff: {message}")
    return parse_name_status(result.stdout)


def evaluate_scope_gate(root: Path, staged_paths: Sequence[str] | None = None) -> ScopeGateResult:
    mode = str(load_config(root)["scope_gate"])
    if mode == "off":
        return ScopeGateResult(mode=mode, checked_paths=[], ignored_paths=[], uncovered_paths=[], active_tasks=[])

    raw_paths = list(staged_paths) if staged_paths is not None else read_staged_diff_paths(root)
    checked_paths, ignored_paths = split_business_paths(raw_paths)
    active = active_task_scopes(load_board(root))
    uncovered = [path for path in checked_paths if not path_is_covered(path, active)]
    return ScopeGateResult(
        mode=mode,
        checked_paths=checked_paths,
        ignored_paths=ignored_paths,
        uncovered_paths=uncovered,
        active_tasks=active,
    )


def split_business_paths(paths: Iterable[str]) -> tuple[list[str], list[str]]:
    checked: set[str] = set()
    ignored: set[str] = set()
    for path in paths:
        normalized = normalize_scope_path(path)
        if not normalized:
            continue
        if is_bookkeeping_path(normalized):
            ignored.add(normalized)
            continue
        checked.add(normalized)
    return sorted(checked), sorted(ignored)


def is_bookkeeping_path(path: str) -> bool:
    return path in BOOKKEEPING_PATHS


def active_task_scopes(board: dict) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for task in active_tasks(board):
        if lock_is_expired(task):
            continue
        scopes = [str(scope) for scope in task.get("scope", []) if str(scope)]
        if not scopes:
            continue
        result.append({"id": str(task.get("id", "")), "owner_agent": str(task.get("owner_agent", "")), "scope": scopes})
    return result


def path_is_covered(path: str, active: Sequence[dict[str, Any]]) -> bool:
    for task in active:
        for scope in task["scope"]:
            if scope and scopes_overlap(scope, path):
                return True
    return False
