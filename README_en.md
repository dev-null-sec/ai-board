# ai-board

English | [中文](./README.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![CLI](https://img.shields.io/badge/CLI-ai--board-0B1F4D)
![License](https://img.shields.io/badge/License-MIT-green)

![ai-board logo](./assets/ai-board.png)

`ai-board` is a small local planning board CLI for AI-assisted software projects.

I built it because long-running AI work gets messy in a very specific way: the code may be fine, but nobody remembers what is currently scheduled, who claimed it, which files are in scope, how it was verified, or what was left behind. `ai-board` keeps that state in one structured file: `.ai-board/board.json`. Markdown boards are generated views for humans and agents to read.

## What It Helps With

- Put new requests into an inbox instead of burying them in chat.
- Schedule and claim work before editing files.
- Record the expected file or directory scope for each active task.
- Block overlapping active scopes by default for safer multi-agent work.
- Complete tasks with real verification and explicit leftovers.
- Initialize AI-native project guardrails: project rules, current status, decisions, roadmap, and board docs.
- Keep multiple lanes, such as platform, content, and docs, inside one board instead of splitting truth across files.

## Install

After the GitHub repository is published, install it as a user-level CLI tool:

```powershell
pipx install "git+https://github.com/dev-null-sec/ai-board.git"
```

If `pipx` is not available but `uv` is:

```powershell
uv tool install "git+https://github.com/dev-null-sec/ai-board.git"
```

Both commands create the global executable:

```powershell
ai-board --help
```

For local development from this repository:

```powershell
uv sync
uv run python -m ai_board --help
```

## Quick Start

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

## For AI Agents

This repository includes a small discovery skill:

```text
skills/ai-board/SKILL.md
```

The skill tells an agent when to use `ai-board` and how to install the CLI. The real usage guide comes from the installed CLI, so it stays matched to the current version:

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
