# Changelog

All notable changes to `ai-board` are documented here.

## v0.1.0-alpha.1 - 2026-05-14

First usable alpha release.

### Added

- AI-native onboarding flow with `ai-board onboard --init-if-missing`.
- Local board source of truth at `.ai-board/board.json`.
- Generated Markdown board views under `docs/`.
- Guardrail document generation through `ai-board init`.
- Task workflow commands: `add`, `schedule`, `start`, `complete`, `archive`, `block`, `status`, `show`.
- Agent identity pool with `agents claim`, `agents list`, and `agents release`.
- Path-level scope locks, lock leases, `renew`, `unlock`, `locks`, and conflict checks.
- Task lanes, sources, acceptance criteria, and simple dependency validation.
- Event log at `.ai-board/events.jsonl` and `history` command.
- `doctor` project health check.
- Project config at `.ai-board/config.json` for language, default lane, default agent kind, and default lease.
- Chinese and English generated board labels.
- Bundled AI usage guide through `ai-board skills get core`.
- GitHub Actions CI for ruff, Python 3.10/3.11/3.12 tests, and wheel/sdist build artifacts.

### Changed

- Business-layer expected errors now use `BoardError` instead of relying on `SystemExit`.
- `complete` releases the task owner's agent identity while keeping ownership history on the task.
- Scope paths are normalized and checked to reject absolute paths and paths that leave the project.
- `board.lock` includes metadata and can recover from stale locks.
- Package metadata now uses SPDX-style `license = "MIT"`.

### Current Boundaries

- This is an alpha release, not a stable workflow engine.
- Scope locking is path-level safety, not semantic code ownership.
- Dependency support is intentionally simple and does not provide a full planning graph.
- SQLite storage, `reopen`, richer agent recovery, PyPI publishing, and static type checking are not included yet.

### Verified

- `ruff check .`
- `python -m unittest discover -s tests`
- `python -m build`
- `ai-board doctor --fail-on-issue`
- `ai-board conflicts --fail-on-conflict`
