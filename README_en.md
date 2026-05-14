# ai-board

English | [中文](./README.md)

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="CLI ai-board" src="https://img.shields.io/badge/CLI-ai--board-0B1F4D">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-green">
</p>

![ai-board logo](./assets/ai-board.png)

A local planning board for AI agents. You talk to the AI about what you need, it schedules, tracks, and prevents conflicts — instead of jumping straight into code.

Current version: `v0.1.0-alpha.1`, the first usable alpha.

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

The basic flow is intentionally small:

```text
You / the AI make a request
        ↓
ai-board CLI writes .ai-board/board.json
        ↓
render generates Markdown boards
        ↓
Humans / agents read the state and continue
```

| Design point | What it means |
| --- | --- |
| Source of truth | `.ai-board/board.json` is the only write target; Markdown boards are generated views. |
| Multi-agent work | Overlapping file scopes are blocked by default; this is path-level safety, not a semantic code lock. |
| Project config | `.ai-board/config.json` can set the default language, lane, agent kind, and lease. |
| Scope lock | Default 240-minute lease; this can be changed in project config. `complete` releases the agent identity, and `archive` moves verified work out of the current board. |
| Lanes | One board can have platform, content, docs, and other lanes while keeping one source of truth. |
| Simple dependencies | Tasks can declare dependencies; `start` blocks unfinished dependencies by default. Complex dependency graphs are out of scope for now. |
| Doctor | `doctor` checks the board, generated docs, event log, scope conflicts, and agent state. |
| History | `history` reads `.ai-board/events.jsonl` and shows task changes. |
| Lifecycle | `inbox → scheduled → active → done → archived`. |

Generated boards are Chinese by default. For English projects, set `language` to `en-US` in `.ai-board/config.json`, then run `ai-board render`.

## FAQ

<details>
<summary><strong>Does ai-board save the AI's chat history or context?</strong></summary>

No. `ai-board` does not dump the model's hidden context into a file, and it does not pretend to restore an entire conversation.

It saves the project facts that need to survive: requests, priority, status, owner, scope, verification, and leftovers. The chat can end and the model can change, but the project plan should not live only in chat history.

</details>

<details>
<summary><strong>Can I edit the Markdown board by hand?</strong></summary>

I would not. The real data lives in `.ai-board/board.json`, which acts like a tiny local database for the tool. `docs/计划看板.md` and `docs/归档计划看板.md` are generated reading views for humans and agents.

If you edit the Markdown directly, the next `ai-board render` can overwrite it. Change task status, owner, scope, verification, and leftovers through the CLI.

</details>

<details>
<summary><strong>Why make it a CLI instead of just writing rules in docs?</strong></summary>

Docs are useful, but an agent can still miss steps: forget to schedule work, forget to declare scope, forget to archive, or have two sessions touch the same files.

The CLI is there to turn the workflow into fixed actions: `add`, `schedule`, `start`, `complete`, `archive`. Conflicts are blocked by the tool, and state changes are written by the tool, so the process does not depend only on the agent remembering every rule.

</details>

<details>
<summary><strong>Does it replace context?</strong></summary>

No, and it should not.

Context is still where you discuss details, trade-offs, and the next judgment call. `ai-board` keeps the project facts that should not disappear. When an agent takes over, it reads the board and docs first, then continues from the current conversation instead of guessing from memory.

</details>

<details>
<summary><strong>Will init overwrite my existing project docs?</strong></summary>

Not by default. `ai-board init` creates AI-native project docs such as `AGENTS.md`, `docs/当前状态.md`, and `docs/开发规范.md`. If a file already exists, it writes a `.example` file instead of replacing your content.

</details>

<details>
<summary><strong>Is this only for Codex?</strong></summary>

No. The repository includes a Codex-friendly skill stub because that is the environment I use most, but the CLI itself is just a command-line tool. Claude, other agents, and humans can use it too. The important bit is that the agent reads `ai-board skills get core` and follows the rules for the installed version.

</details>

<details>
<summary><strong>How much conflict prevention does multi-agent mode provide?</strong></summary>

It catches the common path-overlap case: if one agent has locked `src/api`, another agent cannot start work on `src/api/handler.py` by default.

It does not understand that two different files may still be coupled at the business-logic level, and it is not a cross-machine coordination lock. For real parallel work, keep scopes narrow and task boundaries explicit.

</details>

## Project layout

```text
src/ai_board/          CLI core
skills/ai-board/       Discovery skill for AI agents
tests/                 Tests
docs/                  This project's own planning and status docs
```

## Current boundaries

Not Jira, not a web project manager. This version focuses on a local CLI, JSON as the single source of truth, event logs, doctor checks, multi-agent path-level safety, and generated Markdown views.

| Supported | Not included |
| --- | --- |
| Local CLI | Web login |
| JSON source of truth | Cloud sync |
| Generated Markdown views | Auto-scheduling |
| Simple dependency checks | Complex dependency graphs |
| Event log and `history` | OS-level file locks |
| `doctor` project checks | Semantic code-conflict detection |
| Multi-agent path-level scope safety | Cross-machine coordination locks |

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
