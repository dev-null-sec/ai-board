from __future__ import annotations

from .errors import BoardError

CORE_GUIDE = """---
name: core
description: Core ai-board usage guide. Read this before changing a project board.
---

# ai-board core

`ai-board` is a tiny local CLI for AI agents doing project planning. It keeps
`.ai-board/board.json` as the only write source and renders Markdown views into
`docs/`.

## AI-native entry prompt

When a user gives you the ai-board package name, GitHub URL, invokes
`/ai-board`, or says "use ai-board" without extra instructions, treat it as an
instruction to install or find the CLI and enter onboarding. Do not stop after
`init`.

```text
Install ai-board as a user-level CLI, preferably from PyPI with
pipx install ai-board. If pipx is not available, use uv tool install ai-board.
If an agent skill is needed, copy skills/ai-board/SKILL.md from
https://github.com/dev-null-sec/ai-board.git into the target agent's
skill/skills directory. After installation, run ai-board onboard
--init-if-missing. Follow the onboarding output. Use ai-board skills get core
only when command details are needed.
```

## First checks

```bash
ai-board --help
ai-board onboard --init-if-missing
ai-board agents list
ai-board locks
ai-board next
ai-board status
ai-board conflicts --fail-on-conflict
```

Before editing files, read the active owner and scope locks. If an active task
is owned by another agent and its lock is not expired, do not edit that scope.
Wait for the owner, choose non-overlapping scheduled work, or coordinate an
explicit takeover after the lease expires. Use `ai-board next` to ask the CLI
for non-conflicting candidates before choosing work.

If `ai-board` is not installed, install it as a user-level CLI tool. Do not
silently install it into the current project virtual environment.

Preferred install order:

1. Check for Python 3.10+.
2. Use `pipx` if available.
3. If Python exists but `pipx` does not, install pipx for the current user and
   run it through `python -m pipx`.
4. If the Python/pipx path is not available, use `uv tool install`.

Common commands:

```bash
pipx install ai-board
python -m pip install --user pipx
python -m pipx ensurepath
python -m pipx install ai-board
uv tool install ai-board
pipx install "git+https://github.com/dev-null-sec/ai-board.git"  # source fallback
```

These install methods create the `ai-board` command from the package's console script.

## Skill installation

The CLI and the skill are intentionally separate:

- The CLI does the actual board work.
- The skill lets an agent discover when and how to call the CLI.

After cloning or downloading the repository, copy this file into the skill or
skills directory used by the target agent:

```text
skills/ai-board/SKILL.md
```

Use the target agent's own skill installation rules. If the skill is already in
place, do not duplicate it.

If there is no board yet, or you are unsure whether this is a new or existing
project, use onboarding:

```bash
ai-board onboard --init-if-missing --project-name "Project name"
```

`onboard --init-if-missing` creates the board and guardrail docs when needed,
then classifies the project as empty, lightweight, or existing. It prints the
next question the agent should ask instead of leaving the user at an empty
board.

## Normal workflow

If a user asks you to "use ai-board" in a project, you can follow this compact
prompt:

```text
Use ai-board as the planning source for this project. Run ai-board onboard
--init-if-missing first. If onboarding says the project is empty or lightweight,
ask whether to plan first or write handoff docs from the current files. If it is
an existing project, ask whether to do a handoff summary before scheduling work.
Then run ai-board agents list and ai-board locks. If a non-expired active task
belongs to another agent, do not edit its scope.
Run ai-board next to see non-conflicting candidates and stale generated-board
warnings before choosing a task.
Only edit files after a task is scheduled and started with an honest, narrow
--scope.
Complete tasks with verification and leftovers, then archive them.
```

New requests go to the inbox first:

```bash
ai-board add "Short task title" --priority P1 --lane "平台开发" --source "roadmap" --acceptance "测试通过"
```

Use lanes to separate different work streams while keeping one source of truth.
For example: `平台开发`, `课程内容`, `文档治理`, `默认`.
Dependencies can be declared with `--depends-on`. They must point to existing
tasks, cannot point back to the same task, and simple cycles are rejected.

Project defaults live in `.ai-board/config.json`. If the project usually uses
English, set `language` to `en-US` and run `ai-board render`. The same file can
also set `default_lane`, `default_agent_kind`, and `default_lease_minutes` so
agents do not have to repeat them on every command.

Schedule work before coding:

```bash
ai-board schedule T-0001
```

Claim an agent identity before editing files, then start a scheduled task with
that identity. If another Codex session is already using `codex-00`, the next
claim will return `codex-01`.

```bash
ai-board agents claim --kind codex
ai-board agents list
ai-board start T-0001 --agent codex-00 --scope src/ai_board/cli.py README.md tests/test_cli.py
ai-board locks
ai-board renew T-0001 --agent codex-00
```

`agents claim` reserves a reusable identity with a 240-minute lease by default.
`start` binds that identity to the task, gives the scope lock the same default
lease, and blocks overlapping non-expired active task scopes. Keep `--scope`
narrow: prefer specific files or small subdirectories instead of broad roots
such as `src`, `docs`, `tests`, or `.`. Use `--lease-minutes 0` for no expiry.
`start` also blocks unfinished dependencies unless `--force` is used. Use
`--force` only when the overlap or dependency bypass is intentional and you
have coordinated with the other owner.

If an agent crashes or a scope is no longer needed, release it without
completing the active task:

```bash
ai-board unlock T-0001 --agent codex-00
ai-board agents release codex-00 --force
```

After implementation, complete it with real verification:

```bash
ai-board complete T-0001 --verification "单元测试通过，核心流程手动验收通过" --leftovers "无"
```

`complete` releases the task owner's agent identity so the same AI session can
claim new work. The task keeps `owner_agent` as history. `archive` still has a
compatibility release fallback for older boards.

Then archive it:

```bash
ai-board archive T-0001
```

## Board views

Do not hand-edit generated board Markdown. CLI write commands such as `add`,
`schedule`, `start`, `complete`, and `archive` automatically refresh the
Markdown views after saving `.ai-board/board.json`. Use manual render only as a
repair step after changing config, pulling updates, or seeing a stale generated
doc warning:

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

Expired locks are shown by `locks` and ignored by conflict checks. Renew a lock
before continuing work if you still own the task.

## Useful commands

```bash
ai-board goal "Current delivery goal"
ai-board show T-0001
ai-board status
ai-board next
ai-board history
ai-board history T-0001
```

## Agent rules of thumb

- Read the project rules before coding.
- Add new work to the inbox unless it is already part of the active task.
- Start only scheduled tasks.
- Claim an agent identity such as `codex-00` before starting work; do not reuse a busy non-expired identity.
- Treat active owner and scope locks as a hard gate before coding.
- Use `ai-board next` when active work exists or the Markdown board may be stale.
- Keep scope narrow and honest: prefer concrete files or small subdirectories, not broad roots like `src`, `docs`, `tests`, or `.`.
- Complete tasks only after verification.
- Write verification and leftovers as human-readable summaries. Do not leave archive records as raw command strings only.
- Archive completed tasks so the current board stays short.
"""


FULL_GUIDE = CORE_GUIDE + """

## Command reference

```bash
ai-board init [--project-name NAME] [--force] [--overwrite-docs]
ai-board --lang zh-CN status
ai-board onboard [--init-if-missing] [--project-name NAME]
ai-board goal GOAL
ai-board lang zh-CN
ai-board add TITLE [--priority P0|P1|P2|P3] [--description TEXT] [--lane LANE] [--source TEXT] [--acceptance TEXT] [--depends-on TASK_ID ...]
ai-board schedule TASK_ID
ai-board agents claim [--kind KIND] [--lease-minutes MINUTES]
ai-board agents list
ai-board agents release AGENT_ID [--force]
ai-board start TASK_ID --agent NAME [--scope PATH ...] [--force] [--lease-minutes MINUTES]
ai-board renew TASK_ID --agent NAME [--lease-minutes MINUTES]
ai-board unlock TASK_ID --agent NAME [--force]
ai-board complete TASK_ID --verification TEXT [--leftovers TEXT]
ai-board archive TASK_ID
ai-board block TASK_ID
ai-board status
ai-board next
ai-board conflicts [--fail-on-conflict]
ai-board locks
ai-board history [TASK_ID]
ai-board render
ai-board show TASK_ID [--format human|json]
ai-board skills
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
generated reading views and are normally refreshed by CLI write commands. If
Markdown and JSON disagree, trust JSON and run `ai-board render`.
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
    except KeyError as error:
        available = ", ".join(skill_names())
        raise BoardError(f"Unknown skill: {name}. Available skills: {available}.") from error
    return skill["full_content" if full else "content"]
