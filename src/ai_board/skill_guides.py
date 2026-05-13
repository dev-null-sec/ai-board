from __future__ import annotations


CORE_GUIDE = """---
name: core
description: Core ai-board usage guide. Read this before changing a project board.
---

# ai-board core

`ai-board` is a tiny local CLI for AI-assisted project planning. It keeps
`.ai-board/board.json` as the only write source and renders Markdown views into
`docs/`.

## First checks

```bash
ai-board status
ai-board conflicts --fail-on-conflict
```

If `ai-board` is not installed, install it as a user-level CLI tool:

```bash
pipx install "git+https://github.com/dev-null-sec/ai-board.git"
# or, if pipx is unavailable:
uv tool install "git+https://github.com/dev-null-sec/ai-board.git"
```

Both methods create the `ai-board` command from the package's console script.

If there is no board yet:

```bash
ai-board init --project-name "Project name"
```

`init` creates `.ai-board/board.json`, generated board Markdown, and AI-native
guardrail docs such as `AGENTS.md`, `docs/开发规范.md`, `docs/当前状态.md`,
`docs/决策记录.md`, and `docs/项目方向.md`. Existing guardrail docs are not
overwritten by default; `.example` files are created instead. Use
`ai-board init --overwrite-docs` only when replacing existing guardrail docs is
intentional.

## Normal workflow

New requests go to the inbox first:

```bash
ai-board add "Short task title" --priority P1 --lane "平台开发" --source "roadmap" --acceptance "测试通过"
```

Use lanes to separate different work streams while keeping one source of truth.
For example: `平台开发`, `课程内容`, `文档治理`, `默认`.

Schedule work before coding:

```bash
ai-board schedule T-0001
```

Claim a scheduled task before editing files. Use `--scope` to name the files or
directories you expect to touch:

```bash
ai-board start T-0001 --agent codex --scope src/ai_board README.md tests
ai-board locks
```

`start` blocks overlapping active task scopes by default. Use `--force` only
when the overlap is intentional and you have coordinated with the other owner.

After implementation, complete it with real verification:

```bash
ai-board complete T-0001 --verification "单元测试通过，核心流程手动验收通过" --leftovers "无"
```

Then archive it:

```bash
ai-board archive T-0001
```

## Board views

Do not hand-edit generated board Markdown. Regenerate it from JSON:

```bash
ai-board render
```

Generated files:

- `docs/计划看板.md`
- `docs/归档计划看板.md`

## Conflict checks

Active tasks can declare overlapping scopes. Check before parallel work:

```bash
ai-board locks
ai-board conflicts
ai-board conflicts --fail-on-conflict
```

## Useful commands

```bash
ai-board goal "Current delivery goal"
ai-board show T-0001
ai-board status
```

## Agent rules of thumb

- Read the project rules before coding.
- Add new work to the inbox unless it is already part of the active task.
- Start only scheduled tasks.
- Keep scope narrow and honest.
- Complete tasks only after verification.
- Write verification and leftovers as human-readable summaries. Do not leave archive records as raw command strings only.
- Archive completed tasks so the current board stays short.
"""


FULL_GUIDE = CORE_GUIDE + """

## Command reference

```bash
ai-board init [--project-name NAME] [--force] [--overwrite-docs]
ai-board goal GOAL
ai-board add TITLE [--priority P0|P1|P2|P3] [--description TEXT] [--lane LANE] [--source TEXT] [--acceptance TEXT] [--depends-on TASK_ID ...]
ai-board schedule TASK_ID
ai-board start TASK_ID --agent NAME [--scope PATH ...] [--force]
ai-board complete TASK_ID --verification TEXT [--leftovers TEXT]
ai-board archive TASK_ID
ai-board block TASK_ID
ai-board status
ai-board conflicts [--fail-on-conflict]
ai-board locks
ai-board render
ai-board show TASK_ID
ai-board skills list
ai-board skills get core [--full]
```

## Status lifecycle

```text
inbox -> scheduled -> active -> done -> archived
blocked -> scheduled
```

`archive` is separate on purpose: it forces a verified done task to leave the
current board and become history.

## Storage contract

`.ai-board/board.json` is the source of truth. Markdown files under `docs/` are
generated reading views. If Markdown and JSON disagree, trust JSON and run
`ai-board render`.
"""


SKILLS = {
    "core": {
        "description": "Core ai-board workflow, commands, conflict checks, and agent rules.",
        "content": CORE_GUIDE,
        "full_content": FULL_GUIDE,
    }
}


def skill_names() -> list[str]:
    return sorted(SKILLS)


def get_skill(name: str, full: bool = False) -> str:
    try:
        skill = SKILLS[name]
    except KeyError:
        available = ", ".join(skill_names())
        raise SystemExit(f"Unknown skill: {name}. Available skills: {available}.")
    return skill["full_content" if full else "content"]
