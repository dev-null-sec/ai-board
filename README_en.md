# ai-board

English | [中文](./README.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![CLI](https://img.shields.io/badge/CLI-ai--board-0B1F4D)
![License](https://img.shields.io/badge/License-MIT-green)

![ai-board logo](./assets/ai-board.png)

`ai-board` is a small local planning board CLI for AI agents working on software projects. It is not trying to replace Jira or become a heavy project management system. It just keeps the bits of context that AI development tends to lose.

I built it because long-running AI work gets messy in a very specific way. A request gets added in the middle of a session, another agent joins later, someone asks "what is the current progress?", and the answer often depends on whatever the model can infer from chat history. `ai-board` takes a plainer route: tasks, scheduling, claimed scope, verification, and leftovers live in one structured source of truth: `.ai-board/board.json`. Markdown boards are generated views for humans and agents to read.

## What It Helps With

- New requests go into an inbox instead of getting buried in chat.
- A task must be scheduled, claimed, and given a scope before files are edited.
- Overlapping active scopes are blocked by default, which catches the most obvious multi-agent file collisions.
- Completed work needs real verification and explicit leftovers before it is archived.
- `ai-board init` creates AI-native project docs such as `AGENTS.md`, current status, decision records, and planning boards.
- One board can have multiple lanes, such as platform, content, and docs, while still keeping one source of truth.

This started closer to a skill: Markdown instructions telling the agent how to work. I moved the core workflow into a CLI because docs alone have two problems: copied skills go stale, and multi-agent work needs a stable executable entry point that can read, write, and check conflicts. The current shape is deliberate: the skill helps an agent discover the tool, while the CLI owns the state and serves the version-matched guide.

## AI-Native Install (Recommended)

This is the recommended path: let the agent inspect the machine, install the CLI, place the skill in the target agent's skill directory, then load the version-matched usage guide.

The shortest instruction to give an agent is:

```text
Install ai-board from https://github.com/dev-null-sec/ai-board.git.

Requirements:
1. Install the CLI as a user-level command, not into the current project's virtual environment.
2. Place skills/ai-board/SKILL.md from the repository into the skill/skills directory for the AI agent currently being used, such as Codex, Claude, or another skill-aware tool.
3. After installation, run ai-board skills get core and use that guide to set up an AI-native planning board in the current project.
```

The agent should do two things: install the `ai-board` CLI, and install the discovery skill. The CLI is the executable tool; the skill is what lets Codex, Claude, or another agent discover when to use it.

CLI install order:

1. If `ai-board` already exists, use it.
2. If Python 3.10+ and `pipx` exist, install with `pipx`.
3. If Python 3.10+ exists but `pipx` does not, prepare pipx with `python -m pip install --user pipx`, then install with `python -m pipx install`.
4. If Python/pipx is not usable but `uv` exists, install with `uv tool install`.

For manual installation, do both steps.

First, install the CLI:

```powershell
pipx install "git+https://github.com/dev-null-sec/ai-board.git"
```

If `pipx` is missing but Python is available:

```powershell
python -m pip install --user pipx
python -m pipx ensurepath
python -m pipx install "git+https://github.com/dev-null-sec/ai-board.git"
```

If only `uv` is available:

```powershell
uv tool install "git+https://github.com/dev-null-sec/ai-board.git"
```

These install paths create the global executable:

```powershell
ai-board --help
```

For local development from this repository:

```powershell
uv sync
uv run python -m ai_board --help
```

Second, install the skill: copy this repository file into the skill/skills directory for the AI agent you use.

```text
skills/ai-board/SKILL.md
```

Codex, Claude, and other skill-aware agents each have their own configuration location. Installing only the CLI is enough for manual commands, but the agent may not automatically know when to use it.

## Prompt For Project Use

After `ai-board` is installed, give this to an agent:

```text
Take over the current project and use ai-board to manage the work.

Rules:
1. Run ai-board skills get core first and read the current version's workflow.
2. If .ai-board/board.json does not exist, run ai-board init. Do not overwrite existing guardrail docs.
3. Read AGENTS.md, docs/计划看板.md, docs/当前状态.md, and docs/开发规范.md.
4. Put new requests into the inbox first. Only edit files after the task is scheduled and started.
5. When starting a task, declare an honest --scope so other agents can avoid file collisions.
6. When done, write human-readable verification and leftovers, then archive the task.
```

## Manual Quick Start

Run this in any project root:

```powershell
ai-board init --project-name "my-project"
ai-board goal "Ship the first usable loop"
ai-board add "Build login flow" --priority P1 --lane "Platform" --source "roadmap" --acceptance "manual login flow passes"
ai-board schedule T-0001
ai-board start T-0001 --agent codex --scope frontend/src/Login.tsx
ai-board locks
ai-board complete T-0001 --verification "manual login flow passed" --leftovers "none"
ai-board archive T-0001
```

`init` creates:

```text
.ai-board/board.json
AGENTS.md
docs/开发规范.md
docs/当前状态.md
docs/决策记录.md
docs/项目方向.md
docs/页面设计.md
docs/项目路线/README.md
docs/计划看板.md
docs/归档计划看板.md
```

Existing guardrail docs are not overwritten by default. A sibling `.example` file is created instead. Use this only when you intentionally want to replace them:

```powershell
ai-board init --overwrite-docs
```

## Skill Entry Point

This repository includes a small discovery skill:

```text
skills/ai-board/SKILL.md
```

The skill tells an agent when to use `ai-board`, how to self-check, how to install the CLI, and how to load the version-matched guide. The real usage guide comes from the installed CLI, so it stays matched to the current version:

```powershell
ai-board skills get core
ai-board skills get core --full
```

This follows the same broad shape as `agent-browser`: the skill is the entry point, while the CLI is the executable tool and version-matched manual.

## Common Commands

```powershell
ai-board status
ai-board add "Task title" --priority P1 --lane "Platform"
ai-board schedule T-0001
ai-board start T-0001 --agent codex --scope src README.md
ai-board locks
ai-board conflicts --fail-on-conflict
ai-board complete T-0001 --verification "tests passed" --leftovers "none"
ai-board archive T-0001
ai-board render
ai-board show T-0001
```

Task lifecycle:

```text
inbox -> scheduled -> active -> done -> archived
blocked -> scheduled
```

## How It Works

The project is intentionally small:

- `.ai-board/board.json` is the only write source.
- `docs/计划看板.md` and `docs/归档计划看板.md` are generated views.
- Board writes use a local lock file and atomic replace to avoid corrupted JSON.
- `start` blocks overlapping active scopes by default; use `--force` only when the overlap is intentional.
- `--lane` keeps different work streams in one board.
- Archive verification and leftovers should be written for people, not left as raw command strings.

## Repository Layout

```text
src/ai_board/          CLI, board operations, rendering, and init templates
skills/ai-board/       Discovery skill for AI agents
tests/                 Unit tests
examples/demo-project/ Example rendered board
docs/                  This project's own planning and status docs
assets/                Logo and release assets
```

## Development

```powershell
uv run python -m unittest discover -s tests
ai-board conflicts --fail-on-conflict
```

To install the local checkout as an editable CLI tool:

```powershell
uv tool install --editable .
```

## Current Boundaries

`ai-board` is not Jira and not a web project management system. The current version focuses on a local CLI, AI handoff rules, JSON as the source of truth, multi-agent scope safety, and generated Markdown views.

Not included right now:

- Web login or hosted service
- Cloud sync and permissions
- Automatic scheduling
- Complex dependency graph planning
- OS-level file locks

Planned follow-ups include lease expiry / renew / unlock for scope locks, and an evaluation of SQLite or an event log backend.

## License

MIT License. See [LICENSE](./LICENSE).
