from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .errors import BoardError
from .guardrails import init_guardrail_docs
from .render import render_docs
from .store import Paths, init_board, load_board

IGNORED_DIRS = {
    ".ai-board",
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}

GENERATED_GUARDRAIL_FILES = {
    "AGENTS.md",
    "docs/开发规范.md",
    "docs/当前状态.md",
    "docs/决策记录.md",
    "docs/项目方向.md",
    "docs/页面设计.md",
    "docs/项目路线/README.md",
    "docs/计划看板.md",
    "docs/归档计划看板.md",
}

PROJECT_MARKERS = {
    "Cargo.toml",
    "Dockerfile",
    "Makefile",
    "compose.yml",
    "docker-compose.yml",
    "go.mod",
    "package.json",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "tsconfig.json",
}

SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".py",
    ".rs",
    ".sh",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
}


@dataclass(frozen=True)
class OnboardResult:
    project_kind: str
    board_state: str
    relevant_files: list[str]
    marker_files: list[str]
    source_files: list[str]
    docs_need_fill: bool


def board_exists(root: Path) -> bool:
    return Paths(root.resolve()).board_file.exists()


def relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def should_ignore(path: Path, root: Path) -> bool:
    rel = relative_path(root, path)
    parts = set(path.relative_to(root).parts)
    return bool(parts & IGNORED_DIRS) or rel in GENERATED_GUARDRAIL_FILES


def scan_project_files(root: Path, limit: int = 200) -> list[str]:
    files: list[str] = []
    if not root.exists():
        return files
    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        dirnames[:] = sorted(name for name in dirnames if name not in IGNORED_DIRS)
        for filename in sorted(filenames):
            if len(files) >= limit:
                return files
            path = current_path / filename
            if should_ignore(path, root):
                continue
            files.append(relative_path(root, path))
    return files


def docs_still_placeholder(root: Path) -> bool:
    for relative in ("docs/当前状态.md", "docs/项目方向.md"):
        path = root / relative
        if path.exists() and "待填写" in path.read_text(encoding="utf-8"):
            return True
    return False


def classify_project(files: list[str]) -> tuple[str, list[str], list[str]]:
    marker_files = [path for path in files if Path(path).name in PROJECT_MARKERS]
    source_files = [path for path in files if Path(path).suffix in SOURCE_EXTENSIONS]
    if not files:
        return "empty", marker_files, source_files
    if marker_files or len(source_files) >= 4:
        return "existing", marker_files, source_files
    return "lightweight", marker_files, source_files


def onboard_project(root: Path, project_name: str = "", init_if_missing: bool = False) -> OnboardResult:
    root = root.resolve()
    board_state = "existing"
    if not board_exists(root):
        if not init_if_missing:
            raise BoardError("Board not found. Run `ai-board onboard --init-if-missing` or `ai-board init` first.")
        board = init_board(root, project_name)
        init_guardrail_docs(root)
        render_docs(root, board)
        board_state = "created"
    else:
        load_board(root)

    files = scan_project_files(root)
    project_kind, marker_files, source_files = classify_project(files)
    return OnboardResult(
        project_kind=project_kind,
        board_state=board_state,
        relevant_files=files,
        marker_files=marker_files,
        source_files=source_files,
        docs_need_fill=docs_still_placeholder(root),
    )


def format_onboard_result(result: OnboardResult) -> str:
    lines = [
        "# ai-board onboarding",
        "",
        f"- board: {result.board_state}",
        f"- project_kind: {result.project_kind}",
        f"- relevant_files: {len(result.relevant_files)}",
        f"- marker_files: {', '.join(result.marker_files[:8]) or 'none'}",
        f"- source_files: {len(result.source_files)}",
        f"- docs_need_fill: {'yes' if result.docs_need_fill else 'no'}",
        "",
        "## AI next step",
    ]
    if result.project_kind == "empty":
        lines.extend(
            [
                "STOP: 项目方向尚未与用户确认。",
                "这是一个空项目或几乎空项目。不要直接开始编码。",
                "不要仅根据目录名、文件名或少量 evidence 推断项目目标、初版范围或路线。",
                "在用户确认前，只能记录已知事实、待确认假设和需要询问的问题。",
                "",
                "请问用户：",
                "1. 这个项目最终想解决什么问题？",
                "2. 面向谁使用？人、AI、练习者、开发者，还是内部工具？",
                "3. 第一版只做到什么程度算完成？",
                "4. 现有文件是正式方向、草稿，还是可以推翻重来？",
                "",
                "用户确认后，再把“补齐项目方向和初始计划”写入需求池并排期；确认前不要排实现任务。",
            ]
        )
    elif result.project_kind == "lightweight":
        lines.extend(
            [
                "STOP: 项目方向尚未与用户确认。",
                "这是一个轻量新项目：已有少量代码或文档，但还不足以稳定接手。",
                "不要仅根据目录名、文件名或少量 evidence 推断项目目标、初版范围或路线。",
                "在用户确认前，只能记录已知事实、待确认假设和需要询问的问题。",
                "",
                "请问用户：",
                "1. 当前文件代表正式方向、早期草稿，还是只是一组实验片段？",
                "2. 这个项目最终想解决什么问题，第一版做到哪里算完成？",
                "3. 是否先根据当前文件整理一版事实清单和待确认问题，再与你确认项目方向？",
                "",
                "得到用户确认后，再整理 docs/当前状态.md、docs/项目方向.md、风险和下一步计划；确认前不要排实现任务。",
            ]
        )
    else:
        lines.extend(
            [
                "这是一个已有项目。不要只靠聊天记录判断进度。",
                "",
                "请问用户：",
                "是否先根据当前代码和文档做一次项目接手梳理，补齐 docs/当前状态.md、docs/项目方向.md、重要目录、技术栈、风险和下一步建议？",
                "",
                "用户确认后，把“梳理项目接手文档”作为 P0 任务进入需求池或直接排入下一批。",
            ]
        )

    lines.extend(
        [
            "",
            "## Suggested commands after user confirms",
            "",
            "```bash",
            'ai-board add "梳理项目接手文档" --priority P0 --lane "项目接手" --source "onboard" --acceptance "docs/当前状态.md 已反映真实项目状态" --acceptance "docs/项目方向.md 已写清目标、范围和暂不做"',
            "ai-board schedule <returned-task-id>",
            "ai-board start <returned-task-id> --agent <agent-name> --scope docs AGENTS.md README.md",
            "```",
            "",
            "如果用户只触发了 /ai-board 或只说“用 ai-board 接手”，AI 应默认执行本 onboarding 流程，并向用户提出上面的问题。对于 empty/lightweight 项目，用户确认方向前不要运行上面的排期命令。",
        ]
    )
    return "\n".join(lines)
