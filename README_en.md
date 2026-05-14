# ai-board

English | [中文](./README.md)

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="CLI ai-board" src="https://img.shields.io/badge/CLI-ai--board-0B1F4D">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-green">
</p>

![ai-board logo](./assets/ai-board.png)

A local planning board for AI agents. You talk to the AI about what you need, it schedules, tracks, and prevents conflicts — instead of jumping straight into code.

## Why I built this

The biggest pitfall in AI-assisted coding isn't code quality — it's context management.

You tell the AI "fix this", it fixes it. You ask for another change, it does that too. A few rounds later you ask "where were we with the original plan?" — and it's forgotten, because the ad-hoc requests overwrote the earlier context.

`ai-board` solves exactly this: the AI doesn't drop your previous plan just because you have a new request. Everything goes through scheduling. Urgent bugs get high priority and jump the queue, but they don't derail the overall rhythm.

When you first set up a project, `ai-board` also scaffolds a set of development docs — project direction, current status, decision records, working rules. It's not the main selling point, but it does mean your project has a written foundation from day one.

## How to use it with AI

`ai-board` is built for AI agents. You don't need to memorize commands — you talk to the AI, it does the work.

### Starting a new project

Tell the AI:

```text
Use ai-board to plan this project out before we start coding
```

The AI runs `ai-board onboard --init-if-missing`, then asks you about goals, tech stack, and initial scope. Once you're aligned, it writes the direction into docs and puts concrete tasks on the board. Code comes after planning, not before.

### Taking over an existing project

Tell the AI:

```text
Use ai-board to take over this project
```

The AI scans the project structure, sorts out the current state, and generates docs covering direction, tech stack, risks, and next steps. From that point on, all development goes through the board — no more guessing progress from chat history.

### Making requests

This is the scenario you'll use most. Before, you might say:

```text
There's a bug here, fix it
```

or:

```text
Change this page to look like xxx
```

The AI jumps in and does it. You ask for something else, it does that too. A few rounds later, the original plan is gone.

Now you say:

```text
There's a bug here, add it to the board
```

```text
Change this page to look like xxx — schedule it for the next batch
```

The AI schedules the request instead of acting on it immediately. Urgent bugs get flagged as high priority and handled first, but nothing else gets dropped. You can always ask "what are we working on?" and the AI shows you the board — not a guess from chat history.

## Installation

The recommended way: let the AI handle installation and setup. One sentence:

```text
Install ai-board from https://github.com/dev-null-sec/ai-board.git, then run ai-board onboard --init-if-missing to take over this project.
```

The agent checks your environment, installs the CLI, places the skill file, and loads the version-matched guide. No manual steps required.

If you prefer to install it yourself:

```powershell
pipx install "git+https://github.com/dev-null-sec/ai-board.git"
```

No `pipx` but have `uv`:

```powershell
uv tool install "git+https://github.com/dev-null-sec/ai-board.git"
```

## Command cheat sheet

Most of the time you won't need commands — just talk to the AI. But if you want to check status or operate manually:

```powershell
ai-board status                      # task distribution
ai-board show T-0001                 # task details
ai-board render                      # regenerate Markdown board
```

Full command reference: `ai-board --help` or `ai-board skills get core --full`.

## How it works

A few deliberate design choices:

- `.ai-board/board.json` is the only write target; Markdown boards are generated
- Multiple agents working at the same time get their overlapping file scopes blocked by default
- Scope locks have a 240-minute lease and auto-release
- One board, multiple lanes (platform, content, docs…), one source of truth
- Task lifecycle: `inbox → scheduled → active → done → archived`

## Project layout

```text
src/ai_board/          CLI core
skills/ai-board/       Discovery skill for AI agents
tests/                 Tests
docs/                  This project's own planning and status docs
```

## Current boundaries

Not Jira, not a web project manager. This version focuses on a local CLI, JSON as the single source of truth, multi-agent scope safety, and generated Markdown views.

Not included: web login, cloud sync, auto-scheduling, complex dependency graphs, OS-level file locks.

## Development

```powershell
uv sync
uv run python -m unittest discover -s tests
```

To install the local checkout as an editable CLI:

```powershell
uv tool install --editable .
```

## License

MIT License. See [LICENSE](./LICENSE).
