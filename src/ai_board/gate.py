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
HOOK_MARKER = "# ai-board managed pre-commit hook"
PRE_COMMIT_HOOK = "pre-commit"


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


@dataclass(frozen=True)
class HookStatus:
    status: str
    path: Path | None
    git_root: Path | None
    detail: str = ""

    @property
    def is_git_repo(self) -> bool:
        return self.status not in ("git-missing", "not-git")


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


def pre_commit_hook_content() -> str:
    return "\n".join(
        [
            "#!/bin/sh",
            HOOK_MARKER,
            "# Checks staged files against active ai-board task scope.",
            'repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"',
            'cd "$repo_root" || exit 1',
            "ai-board gate pre-commit",
            "",
        ]
    )


def pre_commit_manual_merge_snippet() -> str:
    return "\n".join(
        [
            "# ai-board scope gate",
            'repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"',
            '(cd "$repo_root" && ai-board gate pre-commit) || exit 1',
        ]
    )


def _run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=5,
            check=False,
        )
    except FileNotFoundError as error:
        raise BoardError("Git is not available. Install git before using hooks.") from error
    except subprocess.TimeoutExpired as error:
        raise BoardError("Git command timed out.") from error


def inspect_pre_commit_hook(root: Path) -> HookStatus:
    try:
        root_result = _run_git(root, ["rev-parse", "--show-toplevel"])
    except BoardError as error:
        return HookStatus(status="git-missing", path=None, git_root=None, detail=str(error))
    if root_result.returncode != 0:
        detail = (root_result.stderr or root_result.stdout or "").strip()
        return HookStatus(status="not-git", path=None, git_root=None, detail=detail)

    git_root = Path((root_result.stdout or "").strip()).resolve()
    hook_result = _run_git(root, ["rev-parse", "--git-path", "hooks/pre-commit"])
    if hook_result.returncode != 0:
        detail = (hook_result.stderr or hook_result.stdout or "").strip()
        return HookStatus(status="unknown", path=None, git_root=git_root, detail=detail)

    raw_path = Path((hook_result.stdout or "").strip())
    hook_path = raw_path if raw_path.is_absolute() else (root / raw_path)
    hook_path = hook_path.resolve()
    if not hook_path.exists():
        return HookStatus(status="missing", path=hook_path, git_root=git_root)
    try:
        content = hook_path.read_text(encoding="utf-8")
    except OSError as error:
        return HookStatus(status="unknown", path=hook_path, git_root=git_root, detail=str(error))
    if HOOK_MARKER in content:
        return HookStatus(status="managed", path=hook_path, git_root=git_root)
    return HookStatus(status="foreign", path=hook_path, git_root=git_root)


def install_pre_commit_hook(root: Path) -> HookStatus:
    status = inspect_pre_commit_hook(root)
    if not status.is_git_repo:
        raise BoardError("pre-commit hook can only be installed in a git work tree.")
    if status.status == "foreign":
        return status
    if status.path is None:
        raise BoardError("Could not resolve .git/hooks/pre-commit.")
    status.path.parent.mkdir(parents=True, exist_ok=True)
    status.path.write_text(pre_commit_hook_content(), encoding="utf-8")
    try:
        status.path.chmod(status.path.stat().st_mode | 0o111)
    except OSError:
        pass
    return inspect_pre_commit_hook(root)


def uninstall_pre_commit_hook(root: Path) -> HookStatus:
    status = inspect_pre_commit_hook(root)
    if not status.is_git_repo:
        raise BoardError("pre-commit hook can only be uninstalled in a git work tree.")
    if status.status != "managed":
        return status
    if status.path is None:
        raise BoardError("Could not resolve .git/hooks/pre-commit.")
    status.path.unlink()
    return inspect_pre_commit_hook(root)


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
