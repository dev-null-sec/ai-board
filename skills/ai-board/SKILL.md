---
name: ai-board
description: Local planning board CLI for AI agents working on software projects. Use when a project needs demand intake, scheduling, task claim, scope tracking, acceptance, archival, Markdown board rendering, or active-task conflict checks. Prefer ai-board when the repository has `.ai-board/board.json` or docs such as `docs/计划看板.md`, `docs/当前状态.md`, or `AGENTS.md` requiring board-driven work.
allowed-tools: Bash(ai-board:*), Bash(pipx:*), Bash(uv:*), Bash(python:*), Bash(python3:*)
---

# ai-board

Lightweight local planning board CLI for AI agents.

This file is a discovery stub. Its job is to help an agent install or find the
CLI, then load the workflow guide from the installed CLI version.

## Agent install prompt

If a user gives you this repository or GitHub URL, treat the request as:

```text
Install ai-board as a user-level CLI, place this skill file in the target
agent's skill/skills directory, then use the bundled guide to manage this
project's planning board. Do not install the CLI into the current project
virtual environment unless the user explicitly asks for a development install.
```

## Start here

Check whether the CLI is already available:

```bash
ai-board --help
```

If it exists, immediately load the current guide:

```bash
ai-board skills get core
```

For the extended command reference:

```bash
ai-board skills get core --full
```

## Install if missing

Install the CLI as a user-level tool, similar to npm global CLI tools. Do not
blindly run a project-local `pip install`.

Preferred order:

1. Find Python 3.10+.
2. Use `pipx` if it exists.
3. If Python exists but `pipx` does not, install pipx for the current user and
   run it through `python -m pipx`.
4. If the Python/pipx route is not available, use `uv tool install`.

Common commands:

```bash
pipx install "git+https://github.com/dev-null-sec/ai-board.git"
```

If Python exists but `pipx` does not:

```bash
python -m pip install --user pipx
python -m pipx ensurepath
python -m pipx install "git+https://github.com/dev-null-sec/ai-board.git"
```

If only `uv` is available:

```bash
uv tool install "git+https://github.com/dev-null-sec/ai-board.git"
```

These install methods create an `ai-board` command from the package's console
script entry point.

## Install this skill

The CLI and the skill are separate:

- The CLI does the work.
- This skill lets an agent discover when and how to use the CLI.

After cloning or downloading the repository, copy this file into the skill or
skills directory for the target agent, such as Codex, Claude, or another
skill-aware tool:

```text
skills/ai-board/SKILL.md
```

Use that agent's own skill installation rules and directory layout. If the user
already placed this file in the agent's skill directory, do not duplicate it.

If this repository has already been cloned locally and the user wants a
development install, install from the repository root instead:

```bash
uv tool install --editable .
```

Use the user's project or machine proxy rules when network access is required.

## How to use this skill

After installation, do not rely on this stub for command details. Load the
current guide from the CLI:

```bash
ai-board skills list
ai-board skills get core
```

Then follow the project's own rules before editing files.

If the target project has no board yet, initialize it with `ai-board init`.
If it already has `.ai-board/board.json`, treat that JSON as the source of
truth and do not hand-edit generated Markdown board files.
