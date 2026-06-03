# ai-board

A local planning board for AI agents. It records requests, scheduling, active file scope, verification, and leftovers so an agent taking over a project does not have to guess from chat history alone.

English | [中文](https://github.com/dev-null-sec/ai-board/blob/v0.1.20/README.md)

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="CLI ai-board" src="https://img.shields.io/badge/CLI-ai--board-0B1F4D">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-green">
</p>

![ai-board logo](https://raw.githubusercontent.com/dev-null-sec/ai-board/v0.1.20/assets/ai-board.png)

Current stable version: `v0.1.20`.

## Why this exists

AI-assisted coding often gets messy because project state has no stable place to live.

A request comes in, the agent starts editing. A bug interrupts it, the agent edits again. After a few rounds, the original plan, the current task status, and the files already touched by another session can all be scattered across chat.

`ai-board` keeps the durable project facts: what was requested, where it is scheduled, who is working on it, which files are in scope, what verification ran, and what remains. Chat can keep handling judgment and discussion; the board keeps recoverable state.

This is intentionally local. No web app, no account, no background service. One repository gets one `.ai-board/board.json`, plus generated Markdown boards for humans and agents to read.

## Quick Start

Most of the time, let the agent install and enter the project for you:

```text
Install ai-board and take over this project:
1. Prefer pipx install ai-board for a user-level CLI.
2. If pipx is unavailable, use uv tool install ai-board.
3. After installation, run ai-board onboard --init-if-missing.
4. Install the agent skill according to that agent's skill rules by copying skills/ai-board/SKILL.md from https://github.com/dev-null-sec/ai-board.git into the agent's skills directory, unless that agent already has this skill installed.
```

Manual install:

```powershell
pipx install ai-board
```

If `pipx` is unavailable but `uv` exists:

```powershell
uv tool install ai-board
```

To try the current source version from GitHub:

```powershell
pipx install "git+https://github.com/dev-null-sec/ai-board.git"
```

## How Humans And AI Work Together

`ai-board` is meant to sit behind the conversation. The human describes intent; the agent installs, onboards, schedules, starts work, records verification, and archives finished tasks. The prompt should be short and precise; the detailed rules live in the tool guide.

### First takeover

Give the agent this prompt:

```text
Use ai-board to take over this project.
Run onboarding first. If key context is missing, ask me; do not guess the direction or start coding.
```

That is enough for the agent to handle installation, initialization, and the built-in guide. Empty projects should start with goal, users, and first-version scope; existing projects should start with current state.

### New requests

Instead of asking the agent to casually "just fix this", route the request through the board:

```text
Put this request into ai-board.
Check whether it belongs to the current task; if not, schedule it before coding.
```

For urgent work:

```text
This needs priority handling.
Record why it jumps the queue, then start it, declare scope, change it, and verify it.
```

### Multi-agent work

Solo-agent mode is the default. When two AI sessions really need to work in parallel, ask one of them to enable multi-agent mode first:

```text
Enable ai-board multi-agent work.
Each session claims an identity; check scopes before editing and close notices before finishing.
```

### Checking progress

Ask the agent in normal language:

```text
Check ai-board: what is active, and what should happen next?
```

The agent can use `status`, `next`, `show`, and `doctor` behind the scenes. The human side is mostly about confirming direction, priority, and acceptance.

## What It Stores

| Data | Location |
| --- | --- |
| Tasks, status, owner, scope, verification | `.ai-board/board.json` |
| Current board | `docs/计划看板.md` |
| Archived board | `docs/归档计划看板.md` |
| Event history | `.ai-board/events.jsonl` |
| Agent notices | `.ai-board/messages.jsonl` |

`board.json` is the write source. Markdown is generated for reading. Task status, dependencies, scope, and verification need stable structured fields; Markdown is easier to read but too easy to accidentally reshape.

Task `scope` describes the user-facing work for that task. CLI writes to `.ai-board/board.json`, event/message logs, and generated boards are ai-board bookkeeping side effects; do not add them to every task scope unless the task itself is manually changing those files.

## Defaults

| Design | Current behavior |
| --- | --- |
| Solo-agent work | Lightweight by default. No mandatory multi-agent notice cleanup or scope-conflict blocking. |
| Multi-agent work | Project-level opt-in, off by default. |
| Git | Default `git_integration=suggest`; missing git is reported, but `git init` is not run silently. |
| Board language | Chinese by default, configurable to `en-US`. |
| Scope | Tracks files or small directories. It is not semantic code-conflict detection. |

Enable multi-agent mode:

```powershell
ai-board config set multi_agent_enabled true
```

After that, overlapping scopes are blocked, `next --agent` shows notices, and `complete` / `archive` warn about unresolved messages. In solo-agent work, ai-board does not make every task deal with notices or active-scope conflicts.

Require git for a project:

```powershell
ai-board config set git_integration required
```

Disable git checks for throwaway work:

```powershell
ai-board config set git_integration off
```

## FAQ

<details>
<summary><strong>Why not manage tasks directly in Markdown?</strong></summary>

Markdown is good to read, but weak as structured state. Status, owner, scope, dependencies, and verification need reliable reads and writes. If the formatting drifts, the tool can no longer tell structure from prose.

`ai-board` stores state in JSON and renders Markdown boards from it.

</details>

<details>
<summary><strong>Can I edit the Markdown board by hand?</strong></summary>

Not recommended. The next CLI write or `ai-board render` can overwrite generated Markdown. Use the CLI to change task status, owner, scope, and verification.

</details>

<details>
<summary><strong>Why doesn't it automatically run git init?</strong></summary>

AI development is much safer with a rollback point, but the project root, parent repositories, temporary folders, large files, secrets, and pre-existing unfinished changes may all need confirmation. `ai-board` reports missing git; it does not silently initialize git or commit user changes.

</details>

<details>
<summary><strong>How much conflict prevention does multi-agent mode provide?</strong></summary>

It only catches path overlap. If one task locks `src/api`, another task touching `src/api/handler.py` is blocked when multi-agent mode is enabled.

It does not understand business coupling between different files, and it is not a cross-machine lock. Parallel work still needs narrow scopes and clear task boundaries.

</details>

<details>
<summary><strong>Is this only for Codex?</strong></summary>

No. The repository includes a Codex-friendly skill stub, but the CLI is a normal command-line tool. Claude, other agents, and humans can use it. The important part is that the agent reads `ai-board skills get core` and follows the rules for the installed version.

</details>

## Current Boundaries

| Supported | Not included |
| --- | --- |
| Local CLI | Web login |
| JSON source of truth | Cloud sync |
| Generated Markdown boards | Hand-written Markdown as the database |
| Event log and `history` | Full audit platform |
| `doctor` project checks | Semantic code-conflict detection |
| Git-first hints and required gate | Silent git initialization or auto-commits |
| Optional multi-agent path-level scope safety | Cross-machine coordination locks |
| Lightweight agent notices | Real-time chat system |

## Project Layout

```text
src/ai_board/          CLI core
skills/ai-board/       Discovery skill for AI agents
tests/                 Tests
docs/                  This project's own planning and status docs
examples/demo-project/ Demo project
```

## Development

```powershell
uv sync
uv run python -m unittest discover -s tests
uv run --with ruff ruff check .
```

Install the local checkout as the active CLI:

```powershell
uv tool install --editable .
```

Release checks:

```powershell
uv run ai-board conflicts --fail-on-conflict
uv run ai-board doctor --fail-on-issue
uv run --with build python -m build
uv run --with twine twine check dist/*
```

## License

MIT License. See [LICENSE](./LICENSE).
