from __future__ import annotations

from pathlib import Path
from typing import Any

from .store import PRIORITIES, Paths, load_config

PRIORITY_ORDER = {priority: index for index, priority in enumerate(PRIORITIES)}
DEFAULT_LANE = "默认"

TEXT = {
    "zh-CN": {
        "status_titles": {
            "active": "正在进行",
            "scheduled": "下一批",
            "inbox": "需求池",
            "blocked": "阻塞 / 待确认",
            "done": "已完成待归档",
        },
        "board_title": "计划看板",
        "archive_title": "归档计划看板",
        "generated_note": "自动生成。唯一写入源是 `.ai-board/board.json`。",
        "archive_note": "自动生成。归档数据来自 `.ai-board/board.json`。",
        "current_goal": "当前目标",
        "empty_goal": "待填写：这一阶段最重要的交付目标是什么。",
        "empty": "- [ ] 暂无",
        "columns": ["ID", "优先级", "任务", "负责人", "Scope", "来源"],
        "unset": "未填写",
        "unassigned": "未指定",
        "undeclared": "未声明",
        "details_title": "**验收 / 依赖**",
        "acceptance": "验收",
        "depends_on": "依赖",
        "colon": "：",
        "after_colon": "",
        "done_rules": [
            "## 本轮完成后归档规则",
            "",
            "- 完成任务后必须写入验收结果。",
            "- 验收结果和遗留问题要写给人看的中文摘要；可以包含关键命令，但不要只贴命令串。",
            "- 没有遗留问题时明确写“无”。",
            "- 已完成任务归档到 `docs/归档计划看板.md`。",
            "- 每轮最多推进 3 个已排期任务；大任务 1-2 个就应停下来汇报。",
        ],
        "no_archive": "暂无归档。",
        "archive_fields": {
            "status": "状态",
            "priority": "优先级",
            "owner": "负责人",
            "verify_scope": "验证范围",
            "verification": "验收结果",
            "deferred_verification": "延后验收",
            "archived_at": "归档时间",
            "leftovers": "遗留问题",
        },
        "none": "无",
        "not_recorded": "未记录",
    },
    "en-US": {
        "status_titles": {
            "active": "In Progress",
            "scheduled": "Next Up",
            "inbox": "Inbox",
            "blocked": "Blocked / Needs Decision",
            "done": "Done, Not Archived",
        },
        "board_title": "Planning Board",
        "archive_title": "Archived Planning Board",
        "generated_note": "Generated file. The only write source is `.ai-board/board.json`.",
        "archive_note": "Generated file. Archive data comes from `.ai-board/board.json`.",
        "current_goal": "Current Goal",
        "empty_goal": "TODO: the most important delivery goal for this phase.",
        "empty": "- [ ] None",
        "columns": ["ID", "Priority", "Task", "Owner", "Scope", "Source"],
        "unset": "Not filled",
        "unassigned": "Unassigned",
        "undeclared": "Undeclared",
        "details_title": "**Acceptance / Dependencies**",
        "acceptance": "acceptance",
        "depends_on": "depends on",
        "colon": ":",
        "after_colon": " ",
        "done_rules": [
            "## Archive Rules After This Round",
            "",
            "- Completion must include verification.",
            "- Verification and leftovers should be human-readable summaries, not raw command strings only.",
            "- If there are no leftovers, write `None`.",
            "- Archive completed tasks into `docs/归档计划看板.md`.",
            "- Finish at most 3 scheduled tasks per round; stop earlier for large or risky work.",
        ],
        "no_archive": "No archived tasks.",
        "archive_fields": {
            "status": "Status",
            "priority": "Priority",
            "owner": "Owner",
            "verify_scope": "Verification scope",
            "verification": "Verification",
            "deferred_verification": "Deferred verification",
            "archived_at": "Archived at",
            "leftovers": "Leftovers",
        },
        "none": "None",
        "not_recorded": "Not recorded",
    },
}


def text_for(language: str) -> dict[str, Any]:
    return TEXT.get(language, TEXT["zh-CN"])


def task_lane(task: dict[str, Any]) -> str:
    return task.get("lane") or DEFAULT_LANE


def table_cell(value: str, empty_text: str = "未填写") -> str:
    text = value.replace("|", "\\|").replace("\n", "<br>")
    return text or empty_text


def code_items(items: list[str], empty_text: str = "未声明") -> str:
    if not items:
        return empty_text
    return "<br>".join(f"`{table_cell(item)}`" for item in items)


def render_task_table(tasks: list[dict[str, Any]], labels: dict[str, Any]) -> list[str]:
    columns = labels["columns"]
    lines = [
        f"| {' | '.join(columns)} |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for task in tasks:
        lines.append(
            " | ".join(
                [
                    f"| `{task['id']}`",
                    table_cell(task.get("priority", "P2"), labels["unset"]),
                    table_cell(task["title"], labels["unset"]),
                    table_cell(task.get("owner_agent") or labels["unassigned"], labels["unset"]),
                    code_items(task.get("scope", []), labels["undeclared"]),
                    table_cell(task.get("source") or labels["unset"], labels["unset"]),
                ]
            )
            + " |"
        )
    return lines


def render_task_details(tasks: list[dict[str, Any]], labels: dict[str, Any]) -> list[str]:
    detail_lines: list[str] = []
    for task in tasks:
        acceptance = task.get("acceptance", [])
        depends_on = task.get("depends_on", [])
        if not acceptance and not depends_on:
            continue
        if not detail_lines:
            detail_lines.extend(["", labels["details_title"], ""])
        if acceptance:
            detail_lines.append(f"- `{task['id']}` {labels['acceptance']}{labels['colon']}")
            detail_lines.extend(f"  - {item}" for item in acceptance)
        if depends_on:
            detail_lines.append(f"- `{task['id']}` {labels['depends_on']}{labels['colon']}{labels['after_colon']}{', '.join(depends_on)}")
    return detail_lines


def sort_tasks_for_board(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(tasks, key=lambda task: PRIORITY_ORDER.get(task.get("priority", "P2"), len(PRIORITY_ORDER)))


def group_tasks_by_lane(tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    lanes: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        lanes.setdefault(task_lane(task), []).append(task)
    return lanes


def render_current_board(board: dict[str, Any], language: str = "zh-CN") -> str:
    labels = text_for(language)
    project = board.get("project", {})
    goal = project.get("current_goal") or labels["empty_goal"]
    lines = [
        f"# {labels['board_title']}",
        "",
        f"> {labels['generated_note']}",
        "",
        f"## {labels['current_goal']}",
        "",
        goal,
        "",
    ]

    for status, title in labels["status_titles"].items():
        lines.extend([f"## {title}", ""])
        tasks = sort_tasks_for_board([task for task in board["tasks"] if task["status"] == status])
        if tasks:
            lanes = group_tasks_by_lane(tasks)
            for lane in sorted(lanes):
                if len(lanes) > 1 or lane != DEFAULT_LANE:
                    lines.extend([f"### {lane}", ""])
                lines.extend(render_task_table(lanes[lane], labels))
                lines.extend(render_task_details(lanes[lane], labels))
                lines.append("")
        else:
            lines.append(labels["empty"])
            lines.append("")

    lines.extend(labels["done_rules"])
    lines.append("")
    return "\n".join(lines)


def render_archive(board: dict[str, Any], language: str = "zh-CN") -> str:
    labels = text_for(language)
    fields = labels["archive_fields"]
    lines = [
        f"# {labels['archive_title']}",
        "",
        f"> {labels['archive_note']}",
        "",
    ]

    if not board["archive"]:
        lines.append(labels["no_archive"])
        lines.append("")
        return "\n".join(lines)

    for task in board["archive"]:
        lines.extend(
            [
                f"## {task['id']} {task['title']}",
                "",
                f"- {fields['status']}: {task['status']}",
                f"- {fields['priority']}: {task.get('priority', 'P2')}",
                f"- {fields['owner']}: {task.get('owner_agent') or labels['unassigned']}",
                f"- {fields['verify_scope']}: {', '.join(task.get('verify_scope', [])) or labels['none']}",
                f"- {fields['verification']}: {task.get('verification') or labels['unset']}",
                f"- {fields['deferred_verification']}: {task.get('deferred_verification') or labels['none']}",
                f"- {fields['archived_at']}: {task.get('archived_at') or labels['not_recorded']}",
                f"- {fields['leftovers']}: {task.get('leftovers') or labels['none']}",
                "",
            ]
        )
    return "\n".join(lines)


def render_docs(root: Path, board: dict[str, Any]) -> None:
    paths = Paths(root.resolve())
    language = str(load_config(root)["language"])
    paths.docs_dir.mkdir(parents=True, exist_ok=True)
    paths.current_board_doc.write_text(render_current_board(board, language), encoding="utf-8")
    paths.archive_doc.write_text(render_archive(board, language), encoding="utf-8")
