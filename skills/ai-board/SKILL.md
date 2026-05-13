---
name: ai-board
description: Local planning board CLI for AI-assisted software projects. Use when a project needs demand intake, scheduling, task claim, scope tracking, acceptance, archival, Markdown board rendering, or active-task conflict checks. Prefer ai-board when the repository has `.ai-board/board.json` or docs such as `docs/计划看板.md`, `docs/当前状态.md`, or `AGENTS.md` requiring board-driven work.
allowed-tools: Bash(ai-board:*), Bash(pipx:*), Bash(uv:*), Bash(python:*)
---

# ai-board

Lightweight local planning board CLI for AI-assisted projects.

This file is a discovery stub, not the full usage guide. The CLI serves the
workflow content that matches the installed version.

## Start here

Check whether the CLI is already available:

```bash
ai-board skills get core
```

For the extended command reference:

```bash
ai-board skills get core --full
```

## Install if missing

Install the CLI as a user-level tool, similar to npm global CLI tools. Prefer
`pipx`:

```bash
pipx install "git+https://github.com/dev-null-sec/ai-board.git"
```

If `pipx` is not available but `uv` is:

```bash
uv tool install "git+https://github.com/dev-null-sec/ai-board.git"
```

Both install methods create an `ai-board` command from the package's console
script entry point.

If this repository has already been cloned locally for development, install
from the repository root instead:

```bash
python -m pip install -e .
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
