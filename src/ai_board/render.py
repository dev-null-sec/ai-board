from __future__ import annotations

from pathlib import Path
from typing import Any

from .store import PRIORITIES, Paths


STATUS_TITLES = {
    "active": "正在进行",
    "scheduled": "下一批",
    "inbox": "需求池",
    "blocked": "阻塞 / 待确认",
    "done": "已完成待归档",
}

PRIORITY_ORDER = {priority: index for index, priority in enumerate(PRIORITIES)}
DEFAULT_LANE = "默认"


def task_lane(task: dict[str, Any]) -> str:
    return task.get("lane") or DEFAULT_LANE


def table_cell(value: str) -> str:
    text = value.replace("|", "\\|").replace("\n", "<br>")
    return text or "未填写"


def code_items(items: list[str]) -> str:
    if not items:
        return "未声明"
    return "<br>".join(f"`{table_cell(item)}`" for item in items)


def render_task_table(tasks: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| ID | 优先级 | 任务 | 负责人 | Scope | 来源 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for task in tasks:
        lines.append(
            " | ".join(
                [
                    f"| `{task['id']}`",
                    table_cell(task.get("priority", "P2")),
                    table_cell(task["title"]),
                    table_cell(task.get("owner_agent") or "未指定"),
                    code_items(task.get("scope", [])),
                    table_cell(task.get("source") or "未填写"),
                ]
            )
            + " |"
        )
    return lines


def render_task_details(tasks: list[dict[str, Any]]) -> list[str]:
    detail_lines: list[str] = []
    for task in tasks:
        acceptance = task.get("acceptance", [])
        depends_on = task.get("depends_on", [])
        if not acceptance and not depends_on:
            continue
        if not detail_lines:
            detail_lines.extend(["", "**验收 / 依赖**", ""])
        if acceptance:
            detail_lines.append(f"- `{task['id']}` 验收：")
            detail_lines.extend(f"  - {item}" for item in acceptance)
        if depends_on:
            detail_lines.append(f"- `{task['id']}` 依赖：{', '.join(depends_on)}")
    return detail_lines


def sort_tasks_for_board(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(tasks, key=lambda task: PRIORITY_ORDER.get(task.get("priority", "P2"), len(PRIORITY_ORDER)))


def group_tasks_by_lane(tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    lanes: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        lanes.setdefault(task_lane(task), []).append(task)
    return lanes


def render_current_board(board: dict[str, Any]) -> str:
    project = board.get("project", {})
    goal = project.get("current_goal") or "待填写：这一阶段最重要的交付目标是什么。"
    lines = [
        "# 计划看板",
        "",
        "> 自动生成。唯一写入源是 `.ai-board/board.json`。",
        "",
        "## 当前目标",
        "",
        goal,
        "",
    ]

    for status, title in STATUS_TITLES.items():
        lines.extend([f"## {title}", ""])
        tasks = sort_tasks_for_board([task for task in board["tasks"] if task["status"] == status])
        if tasks:
            lanes = group_tasks_by_lane(tasks)
            for lane in sorted(lanes):
                if len(lanes) > 1 or lane != DEFAULT_LANE:
                    lines.extend([f"### {lane}", ""])
                lines.extend(render_task_table(lanes[lane]))
                lines.extend(render_task_details(lanes[lane]))
                lines.append("")
        else:
            lines.append("- [ ] 暂无")
            lines.append("")

    lines.extend(
        [
            "## 本轮完成后归档规则",
            "",
            "- 完成任务后必须写入验收结果。",
            "- 验收结果和遗留问题要写给人看的中文摘要；可以包含关键命令，但不要只贴命令串。",
            "- 没有遗留问题时明确写“无”。",
            "- 已完成任务归档到 `docs/归档计划看板.md`。",
            "- 每轮最多推进 3 个已排期任务；大任务 1-2 个就应停下来汇报。",
            "",
        ]
    )
    return "\n".join(lines)


def render_archive(board: dict[str, Any]) -> str:
    lines = [
        "# 归档计划看板",
        "",
        "> 自动生成。归档数据来自 `.ai-board/board.json`。",
        "",
    ]

    if not board["archive"]:
        lines.append("暂无归档。")
        lines.append("")
        return "\n".join(lines)

    for task in board["archive"]:
        lines.extend(
            [
                f"## {task['id']} {task['title']}",
                "",
                f"- 状态：{task['status']}",
                f"- 优先级：{task.get('priority', 'P2')}",
                f"- 负责人：{task.get('owner_agent') or '未指定'}",
                f"- 验收结果：{task.get('verification') or '未填写'}",
                f"- 归档时间：{task.get('archived_at') or '未记录'}",
                f"- 遗留问题：{task.get('leftovers') or '无'}",
                "",
            ]
        )
    return "\n".join(lines)


def render_docs(root: Path, board: dict[str, Any]) -> None:
    paths = Paths(root.resolve())
    paths.docs_dir.mkdir(parents=True, exist_ok=True)
    paths.current_board_doc.write_text(render_current_board(board), encoding="utf-8")
    paths.archive_doc.write_text(render_archive(board), encoding="utf-8")
