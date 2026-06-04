# ai-board

Getting AI to write code is easy. Keeping the project coherent after ten sessions and three different agents — that's the hard part.

English | [中文](./README.md)

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="CLI ai-board" src="https://img.shields.io/badge/CLI-ai--board-0B1F4D">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-green">
</p>

![ai-board logo](https://raw.githubusercontent.com/dev-null-sec/ai-board/v0.2.0/assets/ai-board.png)

Version `v0.2.0`.

## This is not a kanban tool

If you think `ai-board` is "Trello for the terminal" or "a todo list for AI agents," you're looking at the surface and missing the point.

What it actually does is deeper: **it addresses a blind spot in vibe coding that most AI dev tools ignore — who governs the boundaries when AI is writing the code.**

AI tools help you write faster and better. But nobody's asking what happens to the project after all that AI-written code lands. `ai-board` fills that gap: rules, guardrails, and a set of constraints that let AI check whether it should actually be editing that file right now. It doesn't write code. It manages direction, locks scope, records verification, and prevents boundary violations.

## The core problem of vibe coding

Everyone who builds software with AI goes through the same arc:

Week one: This is incredible. One sentence and the feature is done.

Week two: Things are getting messy. The AI refactored unrelated files without asking. You can't remember which conversation had the right approach. The same feature has been rewritten three times and you don't know which version is current.

Week three: You're afraid to touch anything. The codebase is littered with AI artifacts — some were "probably needed at the time," others were "added along the way." You can't delete them because you're not sure what breaks.

The root cause isn't bad AI. **The root cause is that AI-driven development lacks external governance.** Human development has code review, CI, project management tools, team communication. AI development has... chat history.

`ai-board` bridges that gap: it adapts the constraints that keep human development safe, redesigned for a workflow where the coder is an AI. It doesn't port Jira to the terminal. It asks: _what governance does AI development actually need, that humans take for granted?_

## The governance principles

### 1. AI must not infer project direction on its own

Happens constantly: someone opens an empty directory, says "build me something," and AI sees a folder called `api-server` — so it starts planning routes, middleware, a database. It never asked: REST or GraphQL? Go or Python? Is this a weekend prototype or a production service?

`ai-board onboard` blocks this impulse. It scans the project — empty, lightweight new project, or existing codebase — and **steers the AI toward asking the human about direction before writing a single line.** Guessing project direction from a folder name is the most dangerous thing AI can do at the start. `onboard` guards this entry point.

### 2. Every code change must belong to a task

The phrase "while you're at it" kills more AI projects than bugs do. User says "that variable name is wrong." The AI fixes the variable, optimizes the function signature, refactors the call chain, and adds a caching layer. Three weeks later, nobody knows if that cache was planned or incidental.

`ai-board` requires every change to live under a task. A task has scope (which files it touches), acceptance criteria (how you know it's done), and verification (what was actually tested). New requests go into the inbox. They get scheduled. They get started with explicit scope. They get completed with verification. They get archived.

This isn't bureaucracy. It establishes a project-level rule: **every change should belong to a task with declared scope.** The CLI can't physically stop an AI from editing a file — it doesn't work at that layer — but the combination of AGENTS.md rules and `doctor` checks makes off-scope changes discoverable and traceable.

If a project enables git scope gate, `ai-board` can move that check to the commit boundary: `ai-board gate pre-commit` checks whether staged files are covered by the current active task scope. `scope_gate=suggest` warns only; `scope_gate=required` makes the hook return non-zero and rejects the commit. This is a commit-time gate, not runtime file interception. Standard Git can still bypass local hooks with `--no-verify`.

### 3. Multiple agents must not step on each other

Larger projects sometimes need multiple AI sessions in parallel. But two agents editing the same file simultaneously is a merge conflict waiting to happen.

`ai-board`'s scope locking solves this: when an agent starts a task, it declares file-level scope. If another agent tries to start a task with overlapping scope, it gets blocked. Locks have leases. Agents renew them. When done, the lock releases. This isn't a distributed consistency lock — but at AI-development granularity, it's enough. Two agents won't both edit the same `handler.py` in parallel.

Single-agent mode doesn't enforce any of this. No notices, no conflicts. That's intentional — working alone shouldn't carry team-level overhead.

### 4. "Done" must mean something verifiable

The AI says "completed." Did it? Were acceptance criteria written? Were tests run? Were leftovers documented?

`ai-board complete` requires: verification results (what did you actually run?), leftovers (what's not wrapped up?), and deferred verification (what can't be fully tested right now?). `ai-board doctor` checks: does every active task have scope? Are acceptance criteria filled in? Are any locks expired? Do the generated Markdown boards match the JSON source? Is git initialized?

These aren't nitpicks. They address the weakest link in AI development: **the definition of "done" is far too fuzzy.** The CLI makes it concrete.

## How to use it

### For humans

You're not typing CLI commands. You're talking to an AI. `ai-board`'s interface is natural language.

First time:

> Use ai-board to onboard this project.

The AI installs the CLI, runs onboard, assesses project state, and asks you the right questions. An empty project won't start coding — it'll ask you to confirm direction.

Daily:

> Put this request into ai-board. If it's not part of the current task, schedule it.

The AI decides whether to slot it in, whether to queue it or schedule it directly, what scope to declare, and what acceptance criteria to set.

Checking in:

> What's the status in ai-board? What's next?

The AI runs `status`, `next`, `show` and translates the output into plain language.

**You are not operating a CLI. You are directing an AI. The CLI is the AI's tool, not yours.**

### For AI agents (Claude, Codex, etc.)

Install:

```powershell
pipx install ai-board
```

Onboard:

```powershell
ai-board onboard --init-if-missing
```

This scans the project, initializes the board, generates guardrail docs (AGENTS.md, dev standards, current status, etc.), and outputs a project classification.

Daily workflow:

```powershell
ai-board add "Add user auth" --priority P0 --acceptance "Login returns JWT" --acceptance "Unauthenticated returns 401"
ai-board schedule <task-id>
ai-board start <task-id> --agent claude --scope src/auth src/middleware
# ... do the work ...
ai-board complete <task-id> --verification "All unit tests pass, manually tested login and expiry"
ai-board archive <task-id>
```

For multi-agent collaboration, enable it:

```powershell
ai-board config set multi_agent_enabled true
```

Each agent claims an identity, declares scope on `start`, and `next` flags scope conflicts and blocked candidates.

## How this differs

**vs. Jira / Linear / Trello:** Those are project management tools for humans — built around team collaboration and visualization. `ai-board` is a governance layer for AI agents — built around direction confirmation, scope locking, verification closure, and guardrail generation. The operator is the AI, not the human.

**vs. git:** `ai-board` doesn't replace git — it depends on it. By default it reminds you to initialize git and suggests commits before coding. `git_integration=required` enforces it. AI should always have a rollback point before making changes. Git is the mechanism; `ai-board` is the policy layer that ensures it exists.

**vs. git hooks:** `scope_gate=suggest|required` can work with `ai-board hooks install pre-commit`. The hook checks staged files against active task scope. If you already have your own hook, `ai-board` does not overwrite it; it prints a manual merge snippet instead.

**vs. CLAUDE.md / AGENTS.md:** `ai-board init` generates AGENTS.md and guardrail docs under `docs/`. These files tell the AI: read the board before coding, new requests go to the inbox first, max 1–2 active tasks. Without these rules, AI defaults to "hear something, immediately change something" — catastrophic for multi-session projects.

**vs. a long system prompt:** Some people try to cram governance into a system prompt. Prompts get truncated, forgotten, and aren't shared across agents. `ai-board` puts governance rules in the project's filesystem. Rules are bound to the project, not the agent.

## What it stores

| Data | File | Role |
| --- | --- | --- |
| Tasks, status, scope, locks, verification | `.ai-board/board.json` | Single source of truth |
| Operation history | `.ai-board/events.jsonl` | Auditable change log |
| Inter-agent messages | `.ai-board/messages.jsonl` | Multi-agent notices |
| Current board (human-readable) | `docs/计划看板.md` | Generated view — don't hand-edit |
| Archive board | `docs/归档计划看板.md` | Generated view |
| Guardrail docs | `AGENTS.md`, `docs/开发规范.md`, etc. | AI behavioral constraints |

JSON is for machines. Markdown is for humans. Writes always go through the CLI — the JSON → Markdown pipeline never drifts.

## Project structure

```text
src/ai_board/          CLI core (cli / operations / store / render / guardrails / onboarding / parser / skill_guides)
skills/ai-board/       Discovery skill for Codex and other agents
tests/                 Tests
docs/                  This project's own planning and status docs
examples/demo-project/ Demo project
```

## Boundaries

| Supported | Deliberately excluded |
| --- | --- |
| Local CLI, JSON truth source | Web login, cloud sync |
| Generated Markdown views | Hand-written Markdown as database |
| Single-agent default mode | Mandatory multi-agent overhead |
| Optional multi-agent scope collision prevention | Semantic code conflict detection, cross-machine locks |
| Event log and `history` | Full audit system |
| `doctor` project self-check | Automatic repair |
| Git prompting, required gating, optional pre-commit scope gate | Silent `git init` / `git commit`, runtime file interception |
| AGENTS.md guardrail generation | Automatic guardrail enforcement |

## Development

```powershell
uv sync
uv run python -m unittest discover -s tests
uv run --with ruff ruff check .
```

Install the local working copy:

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
