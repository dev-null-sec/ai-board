from __future__ import annotations

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
    for path in sorted(root.rglob("*")):
        if len(files) >= limit:
            break
        if path.is_dir():
            continue
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
                "这是一个空项目或几乎空项目。不要直接开始编码。",
                "",
                "请问用户：",
                "1. 是否先一起规划项目目标、技术栈、初版范围和验收标准？",
                "2. 如果已有想法，是否先根据用户描述补齐 docs/项目方向.md 和 docs/当前状态.md？",
                "",
                "用户确认后，再把“补齐项目方向和初始计划”写入需求池并排期。",
            ]
        )
    elif result.project_kind == "lightweight":
        lines.extend(
            [
                "这是一个轻量新项目：已有少量代码或文档，但还不足以稳定接手。",
                "",
                "请问用户：",
                "是否先根据当前文件整理一版项目接手文档，包括 docs/当前状态.md、docs/项目方向.md、风险和下一步计划？",
                "",
                "整理完成后，再询问用户是继续规划 plan，还是按当前方向进入需求池排期执行。",
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
            "如果用户只触发了 /ai-board 或只说“用 ai-board 接手”，AI 应默认执行本 onboarding 流程，并向用户提出上面的问题。",
        ]
    )
    return "\n".join(lines)
