from __future__ import annotations

from .errors import BoardError

DETAILED_GUIDE = """---
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
Install the agent skill according to that agent's skill rules by copying
skills/ai-board/SKILL.md from https://github.com/dev-null-sec/ai-board.git into
the target agent's skill/skills directory, unless that agent already has this
skill installed. After installation, run ai-board onboard --init-if-missing.
Follow the onboarding output. Use ai-board skills get core only when command
details are needed.
```

## First checks

```bash
ai-board --help
ai-board onboard --init-if-missing
ai-board next
ai-board status
```

New projects start in solo mode: `multi_agent_enabled=false` in
`.ai-board/config.json`. In solo mode, keep the normal board lifecycle, but do
not require agents to watch inbox notices, coordinate active locks, or resolve
multi-agent conflicts before every ordinary change.

Enable multi-agent coordination only when the project actually has parallel AI
sessions:

```bash
ai-board config set multi_agent_enabled true
ai-board agents list
ai-board locks
ai-board conflicts --fail-on-conflict
```

When multi-agent mode is enabled, read the active owner and scope locks before
editing files. If an active task is owned by another agent and its lock is not
expired, do not edit that scope. Wait for the owner, choose non-overlapping
scheduled work, or coordinate an explicit takeover after the lease expires. Use
`ai-board next` to ask the CLI for non-conflicting candidates before choosing
work.

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

For empty or lightweight projects, treat onboarding as a hard direction gate.
Directory names, file names, and small evidence fragments are only hypotheses,
not project direction. Until the user confirms the goal, audience, first-version
scope, and whether current files are authoritative, you may only record known
facts, list hypotheses, and ask questions. Do not write final roadmap language,
schedule implementation work, or start coding from guessed direction.

## Normal workflow

If a user asks you to "use ai-board" in a project, you can follow this compact
prompt:

```text
Use ai-board as the planning source for this project. Run ai-board onboard
--init-if-missing first. If onboarding says the project is empty or lightweight,
stop and ask the user to confirm the project goal, audience, first-version
scope, and whether current files are authoritative. Do not infer project
direction from directory names, file names, or small evidence fragments. If it
is an existing project, ask whether to do a handoff summary before scheduling
work.
Run ai-board next to see candidate work and stale generated-board warnings
before choosing a task.
If this project uses parallel AI sessions, first enable multi-agent mode with
ai-board config set multi_agent_enabled true, then run ai-board agents list and
ai-board locks. If a non-expired active task belongs to another agent, do not
edit its scope.
Only edit files after a task is scheduled and started with an honest, narrow
--scope.
Complete tasks with verification and leftovers, then archive them.
If a blocked task is stale or no longer needed, archive it with `ai-board
archive TASK_ID` instead of editing `board.json`; if it should continue, reopen
it with `ai-board reopen TASK_ID --reason TEXT`, then start and verify it.
```

New requests go to the inbox first:

```bash
ai-board add "Short task title" --priority P1 --lane "平台开发" --source "roadmap" --acceptance "测试通过" --verify-scope tests
```

Use lanes to separate different work streams while keeping one source of truth.
For example: `平台开发`, `课程内容`, `文档治理`, `默认`.
Dependencies can be declared with `--depends-on`. They must point to existing
tasks, cannot point back to the same task, and simple cycles are rejected.

Project defaults live in `.ai-board/config.json`, but agents should update them
through `ai-board config` instead of hand-editing the file. For example, use
`ai-board config set language en-US` for English projects. The same command can
set `multi_agent_enabled`, `default_lane`, `default_agent_kind`,
`default_lease_minutes`, `git_integration`, and doctor thresholds with
validation.

Git integration is git-first but not silent. New projects default to
`git_integration=suggest`: if the project is not a git work tree, onboarding and
doctor recommend initializing git before coding, but they do not run `git init`
for you. Use `ai-board config set git_integration required` when a project must
have git before AI edits, or `ai-board config set git_integration off` for
temporary throwaway work.

Scope gate is a commit-time check, not a runtime file sandbox. New projects
default to `scope_gate=suggest`: `ai-board gate pre-commit` checks staged files
against active task scope and warns without blocking. Use
`ai-board hooks install pre-commit` to install the managed hook. Set
`scope_gate=required` only when commits outside active task scope should fail.
If a foreign pre-commit hook exists, ai-board prints a merge snippet and does
not overwrite it. Standard Git can still bypass local hooks with `--no-verify`;
for strict projects, run the same gate in CI or release checks too.

Schedule work before coding:

```bash
ai-board schedule T-0001
```

In solo mode, start a scheduled task with a stable agent name. For parallel AI
sessions, claim an agent identity before editing files, then start the task
with that identity. If another Codex session is already using `codex-00`, the
next claim will return `codex-01`.

```bash
ai-board agents claim --kind codex
ai-board agents list
ai-board start T-0001 --agent codex-00 --scope src/ai_board/cli.py README.md tests/test_cli.py
ai-board locks
ai-board renew T-0001 --agent codex-00
```

After `agents claim`, write down the exact identity you received and use that
same identity for the whole task. Do not switch identities in later `start`,
`tell`, `inbox`, `renew`, `unlock`, `complete`, or `archive` commands unless
you intentionally release the old identity and claim another one. If your own
notes or natural-language summary disagree with `agents list`, task owner,
`events.jsonl`, or `messages.jsonl`, trust the structured board records.

Treat `--scope` as the write scope and `--verify-scope` as the verification
dependency scope. If full verification needs files locked by another active
task, record local verification now and explain the deferred full verification
instead of pretending the full suite was stable.

Some paths are shared verification resources, such as `tests`,
`tests/test_cli.py`, and core CLI modules. Do not keep them locked across a
chain of tasks. After releasing shared verification scope, run `ai-board next`
and handle tasks waiting for full verification before starting fresh work.

When multi-agent mode is enabled and `ai-board next` shows active locks, do not
treat that as "nothing can be done". First look for `available` candidates,
then add or schedule a non-overlapping docs/evaluation task if that is useful.
For `needs-scope` candidates, declare a narrow scope and rerun `next`; for
blocked candidates, coordinate with the owner or wait with a recorded reason.
Pause only after this check shows no safe work remains.

`agents claim` reserves a reusable identity with a 240-minute lease by default.
`start` binds that identity to the task, gives the scope lock the same default
lease, and records the write scope. When multi-agent mode is enabled, `start`
also blocks overlapping non-expired active task scopes. `--scope` is required:
use specific files or small subdirectories instead of broad roots such as
`src`, `docs`, `tests`, or `.`. Use `--lease-minutes 0` for no expiry. `start`
always blocks unfinished dependencies unless `--force` is used. Use `--force`
only when the dependency bypass is intentional; in multi-agent mode, also use it
only after coordinating the overlap with the other owner.

If the task boundary changes while it is active, do not run `start` again and
do not hand-edit `board.json`. Update the active task with `rescope`; this
records the new write scope and reacquires the lock:

```bash
ai-board rescope T-0001 --agent codex-00 --scope src/app.py README.md --verify-scope tests/test_app.py
```

If an agent crashes or a scope is no longer needed, release the lock without
completing the active task. `unlock` keeps the task scope as history, but clears
the active lock so other agents are not blocked by that scope:

```bash
ai-board unlock T-0001 --agent codex-00
ai-board agents release codex-00 --force
```

After implementation, complete it with real verification:

```bash
ai-board complete T-0001 --verification "局部测试通过" --deferred-verification "全量测试等待 T-0002 释放 tests/test_cli.py" --leftovers "无"
```

`complete` releases the task owner's agent identity so the same AI session can
claim new work. The task keeps `owner_agent` as history. `archive` still has a
compatibility release fallback for older boards.

Then archive it:

```bash
ai-board archive T-0001
```

If a done or archived task turns out to be unfinished, reopen it with a clear
reason instead of creating a duplicate task:

```bash
ai-board reopen T-0001 --reason "验收发现回归，需要补修"
```

For lightweight cross-agent notices in multi-agent mode, use `tell` and
`inbox`. Notices are not real-time chat and do not change task state; always
trust board locks and task status over message text.

```bash
ai-board tell --from codex-00 --to codex-01 --type wait --task T-0001 "waiting for tests/test_cli.py"
ai-board inbox --agent codex-01
ai-board inbox --agent codex-01 --ack M-0001
ai-board inbox --agent codex-01 --resolve M-0001
ai-board inbox --agent codex-01 --fail-on-unresolved
ai-board next --agent codex-01
```

When you receive a notice, use this response flow:

1. Run `ai-board inbox --agent YOUR_AGENT` and read unresolved notices.
2. Classify each notice type: `wait`, `release`, `handoff`, `request`, or `info`.
3. If it mentions a task or scope, run `ai-board locks`, `ai-board show TASK_ID`,
   and when relevant `ai-board conflicts --fail-on-conflict`. Do not rely on
   message text alone.
4. If you no longer need a locked scope, release it with `ai-board unlock` or
   complete/archive the task. If you still need it, reply with `ai-board tell`
   explaining the reason and expected release condition.
5. If the notice changes task boundaries, update the board through CLI commands;
   never treat a notice as the source of truth.
6. Mark the notice with `--ack` after reading it, and `--resolve` only after you
   have acted, replied, or confirmed it does not affect your work.
7. Before ending your task, run `ai-board inbox --agent YOUR_AGENT
   --fail-on-unresolved`. If it returns non-zero, do not finish or hand off as
   clean. Go back through this response flow: ack/resolve the notice if it is
   handled, or send a `tell` reply explaining why it is still blocked, then run
   the check again.

Use the same claimed identity when sending, reading, acknowledging, or resolving
notices. A model may describe itself with the wrong name in prose; the reliable
identity record is the `--agent` / `--from` value written to the board events
and message log.

## Board views

Do not hand-edit generated board Markdown. CLI write commands such as `add`,
`schedule`, `start`, `complete`, and `archive` automatically refresh the
Markdown views after saving `.ai-board/board.json`. Use manual render only as a
repair step after changing config, pulling updates, or seeing a stale generated
doc warning:

Task `--scope` describes the user's work scope. The board JSON, event/message
logs, and generated Markdown updates are ai-board's own bookkeeping side
effects; do not add them to every task scope unless you are manually editing
those files as the task itself.

```bash
ai-board render
```

Generated files:

- `docs/计划看板.md`
- `docs/归档计划看板.md`

## Conflict checks

Multi-agent conflict checks are project-level opt-in. New projects default to
`multi_agent_enabled=false`, so solo work is not interrupted by notice prompts,
active-lock advice, or automatic scope-conflict blocking. Turn it on per
project before real parallel work:

```bash
ai-board config set multi_agent_enabled true
```

Active tasks can declare overlapping scopes. After enabling multi-agent mode,
check before parallel work:

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
- Check git status before editing when `git_integration` is `suggest` or `required`; do not silently initialize git or commit pre-existing user changes.
- Add new work to the inbox unless it is already part of the active task.
- Start only scheduled tasks.
- Solo mode is the default. Enable multi-agent mode per project with `ai-board config set multi_agent_enabled true` only when parallel AI sessions are actually needed.
- In solo mode, use a stable agent name and normal task lifecycle without mandatory notice cleanup or active-lock coordination.
- In multi-agent mode, claim an agent identity such as `codex-00` before starting work; do not reuse a busy non-expired identity.
- In multi-agent mode, keep using the exact claimed identity across start/tell/inbox/complete/archive; trust board events and message logs over natural-language self-descriptions.
- In multi-agent mode, treat active owner and scope locks as a hard gate before coding.
- Use `ai-board next` when active work exists or the Markdown board may be stale.
- In multi-agent mode, when blocked by active locks, keep looking for `available` work or split out non-overlapping docs/evaluation work before pausing.
- In multi-agent mode, when receiving notices, verify them against board state, act or reply, then ack/resolve explicitly.
- In multi-agent mode, treat a non-zero `inbox --fail-on-unresolved` as a failed handoff until notices are resolved or a blocker reply is sent.
- Declare both write scope and verification scope before relying on test results.
- Release shared verification scope quickly, then prioritize tasks waiting for full verification.
- Keep scope narrow and honest: prefer concrete files or small subdirectories, not broad roots like `src`, `docs`, `tests`, or `.`.
- Complete tasks only after verification.
- Archive stale or no-longer-needed blocked tasks with `ai-board archive TASK_ID`; reopen blocked tasks with `ai-board reopen TASK_ID --reason TEXT` before continuing work.
- Write verification and leftovers as human-readable summaries. Do not leave archive records as raw command strings only.
- Archive completed tasks so the current board stays short.
"""


CORE_GUIDE = """---
name: core
description: Short ai-board handoff checklist. Read this before changing a project board.
---

# ai-board core

`ai-board` keeps `.ai-board/board.json` as the only write source and renders
Markdown views into `docs/`.

## First 60 Seconds

Run these before choosing work:

```bash
ai-board onboard --init-if-missing
ai-board next
ai-board status
```

Then apply the onboarding result:

1. If the project is empty or lightweight, stop and ask the user to confirm the
   goal, audience, first-version scope, and whether current files are
   authoritative. Directory names, file names, and small evidence fragments are
   only hypotheses. Do not write final roadmap language or start coding from
   guessed direction.
2. Check git before editing when `git_integration=suggest` or `required`.
   ai-board may recommend `git init`, `.gitignore`, and an initial commit, but
   it does not run `git init` for you. Do not silently initialize git or commit
   pre-existing user changes.
3. If `scope_gate` is `suggest` or `required`, run `ai-board hooks status` and
   `ai-board gate pre-commit` when needed. This is not runtime file blocking.
4. Treat generated board Markdown as a reading view. Do not hand-edit
   `docs/计划看板.md` or `docs/归档计划看板.md`; use CLI commands and `ai-board render`.
5. Review blocked tasks honestly. Do not archive by age alone. Archive only
   after confirming the task is obsolete, superseded, already satisfied, or no
   longer fits the current project direction; then run `ai-board archive TASK_ID`.
   If it should continue, run `ai-board reopen TASK_ID --reason TEXT`, then
   schedule/start it.
6. If the project direction changed, review inbox, scheduled, and blocked work
   before starting a fresh implementation task.

## Install Prompt

When a user gives you the package name, GitHub URL, `/ai-board`, or says "use
ai-board", install or find the CLI and enter onboarding:

```text
Install ai-board as a user-level CLI, preferably from PyPI with
pipx install ai-board. If pipx is not available, use uv tool install ai-board.
Install the agent skill according to that agent's skill rules by copying
skills/ai-board/SKILL.md from https://github.com/dev-null-sec/ai-board.git into
the target agent's skill/skills directory, unless that agent already has this
skill installed. After installation, run ai-board onboard --init-if-missing.
Follow the onboarding output. Use ai-board skills get core --full only when
command details are needed.
```

## Normal Task Flow

New work goes to the inbox unless it is already part of the active task:

```bash
ai-board add "Short task title" --priority P1 --acceptance "验收标准"
ai-board schedule T-0001
ai-board start T-0001 --agent codex --scope src/app.py README.md
```

Use an honest, narrow `--scope`: concrete files or small subdirectories, not
broad roots such as `src`, `docs`, `tests`, or `.`. If an active task boundary
changes, use `ai-board rescope T-0001 --agent codex --scope <paths...>` instead
of running `start` again or editing `board.json`. If a lock is no longer needed,
`unlock` keeps the task scope as history while releasing the active lock.

Complete only after verification, write leftovers for humans, then archive:

```bash
ai-board complete T-0001 --verification "tests passed" --leftovers "无"
ai-board archive T-0001
```

## Solo vs Multi-Agent

Solo mode is the default: `multi_agent_enabled=false`. In solo mode, use a
stable agent name and the normal lifecycle without mandatory notice cleanup.

Enable multi-agent coordination only when parallel AI sessions are actually
needed:

```bash
ai-board config set multi_agent_enabled true
ai-board agents claim --kind codex
ai-board locks
ai-board conflicts --fail-on-conflict
```

When multi-agent mode is enabled, active owner and scope locks are a hard gate.
Use the exact claimed identity across `start`, `tell`, `inbox`, `complete`, and
`archive`. If notices exist, verify them against board state before acting, then
ack/resolve them explicitly.

## Source Contract

- Source of truth: `.ai-board/board.json`.
- Generated views: `docs/计划看板.md`, `docs/归档计划看板.md`.
- Task `--scope` is for user work. ai-board bookkeeping writes to board JSON,
  logs, and generated docs are system side effects, not extra business scope.
- If Markdown and JSON disagree, trust JSON and run `ai-board render`.
- For command details, run `ai-board skills get core --full`.
"""


FULL_GUIDE = CORE_GUIDE + "\n\n## Detailed workflow\n\n" + DETAILED_GUIDE.partition("# ai-board core\n\n")[2] + """

## Command reference

```bash
ai-board init [--project-name NAME] [--force] [--overwrite-docs]
ai-board --lang zh-CN status
ai-board onboard [--init-if-missing] [--project-name NAME]
ai-board goal GOAL
ai-board lang zh-CN
ai-board config list
ai-board config get KEY
ai-board config set KEY VALUE
ai-board tell --from AGENT --to AGENT|all [--type info|wait|release|handoff|request] [--task TASK_ID] MESSAGE
ai-board inbox --agent AGENT [--ack MESSAGE_ID] [--resolve MESSAGE_ID] [--all] [--fail-on-unresolved]
ai-board add TITLE [--priority P0|P1|P2|P3] [--description TEXT] [--lane LANE] [--source TEXT] [--acceptance TEXT] [--depends-on TASK_ID ...] [--verify-scope PATH ...]
ai-board schedule TASK_ID
ai-board agents claim [--kind KIND] [--lease-minutes MINUTES]
ai-board agents list
ai-board agents release AGENT_ID [--force]
ai-board start TASK_ID --agent NAME [--scope PATH ...] [--force] [--lease-minutes MINUTES]
ai-board renew TASK_ID --agent NAME [--lease-minutes MINUTES]
ai-board rescope TASK_ID --agent NAME --scope PATH ... [--verify-scope PATH ...] [--force] [--lease-minutes MINUTES]
ai-board unlock TASK_ID --agent NAME [--force]
ai-board complete TASK_ID --verification TEXT [--deferred-verification TEXT] [--leftovers TEXT]
ai-board archive TASK_ID
ai-board reopen TASK_ID --reason TEXT
ai-board block TASK_ID
ai-board status
ai-board next [--agent AGENT]
ai-board gate pre-commit
ai-board hooks install pre-commit
ai-board hooks status
ai-board hooks uninstall pre-commit
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
blocked -> archived
```

`archive` is separate on purpose: verified done tasks leave the current board
as history, and stale blocked tasks can be archived instead of hand-editing
`board.json`. If a blocked task should continue, use `reopen --reason` to move
it back to scheduled before starting and completing it.

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
