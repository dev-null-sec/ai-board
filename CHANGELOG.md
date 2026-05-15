# 更新日志

`ai-board` 的重要版本变化会记录在这里。以后 Release 说明和更新日志默认使用中文。

## v0.1.0-alpha.2 - 2026-05-15

第二个 alpha 版本，重点补齐 AI 原生协作闭环、中文 CLI 体验、发布自动化和 PyPI 发布准备。

### 新增

- 新增 `ai-board next`，用于新 agent 接手时读取 active owner、scope lock、lease、生成看板 stale 状态，并推荐不冲突候选任务。
- 新增 CLI 中文输出第一版：可通过 `AI_BOARD_LANG=zh-CN` 或 `--lang zh-CN` 切换人类可读输出。
- 新增中文帮助页和常见参数错误提示；`ai-board -h` 可在中文环境下显示中文命令说明。
- 新增 `ai-board lang`，默认输出 `zh-CN` 的 PowerShell、cmd 和 bash/zsh 环境变量切换提示。
- 新增 `ai-board skills` 裸调默认列出内置 AI 使用指南。
- 新增 `show` 的人类可读默认输出，仍可用 `--format json` 输出结构化 JSON。
- 新增事件日志写入失败 fallback：写失败时输出 warning，并写入 `.ai-board/events.failed.jsonl` 供 `doctor` 提醒。
- 新增过宽 scope 提醒：默认把 `.`, `src`, `docs`, `tests` 视为偏宽 scope，提示 agent 优先使用具体文件或小目录。
- 新增计划看板自动渲染回归测试，覆盖主要 CLI 写操作刷新 Markdown 生成视图。
- 新增 GitHub Actions 发布 workflow，支持通过 PyPI Trusted Publishing 发布包。

### 调整

- 仓库里的 `skills/ai-board/SKILL.md` 收窄为 discovery stub，完整流程以 `ai-board skills get core` 为准，避免 skill 内容和 CLI 版本漂移。
- `ai-board onboard` 会显示当前 active task 的 owner、scope lock、lease 和避让提醒。
- `schedule` / `start` 遇到已 active 任务时，错误信息会带 owner、scope 和 lease，减少新 agent 抢占任务的误判。
- README 和内置 guide 统一说明：CLI 写操作会自动渲染 Markdown 看板，`ai-board render` 是配置变更、拉取后修复或 stale 提示时的兜底命令。
- README FAQ 和版面做了轻量整理，澄清 JSON 是真相源、Markdown 是生成视图、ai-board 不保存聊天上下文。
- `doctor` 增加业务健康检查：active 任务停滞、过宽 scope、空 acceptance、agent lease 即将到期、生成看板 stale、事件日志 fallback 等。

### 当前边界

- 仍是 alpha 版本，暂不承诺稳定 API。
- scope lock 仍是路径级防撞，不做 glob、文件级强制锁或语义冲突判断。
- `ai-board render` 不是后台监听；正常 CLI 写操作会自动渲染，手动 render 作为修复按钮保留。
- PyPI 发布依赖 GitHub Actions 和 PyPI Trusted Publishing 配置。

### 发布前验证

- `uv run python -m unittest discover -s tests`
- `uv run --with ruff ruff check .`
- `uv run python -m build`
- `uv run python -m ai_board doctor --fail-on-issue`
- `uv run python -m ai_board conflicts --fail-on-conflict`

## v0.1.0-alpha.1 - 2026-05-14

首个可试用 alpha 版本。

### 新增

- 新增 AI 原生接手流程：`ai-board onboard --init-if-missing`。
- 使用 `.ai-board/board.json` 作为本地唯一真相源。
- 自动生成 Markdown 看板视图到 `docs/`。
- `ai-board init` 可生成 AI 原生开发规范文档。
- 任务工作流命令：`add`、`schedule`、`start`、`complete`、`archive`、`block`、`status`、`show`。
- Agent 身份池：`agents claim`、`agents list`、`agents release`。
- 路径级 scope lock、锁租约、`renew`、`unlock`、`locks` 和冲突检查。
- 任务泳道、来源、验收标准和简单依赖校验。
- `.ai-board/events.jsonl` 事件日志和 `history` 命令。
- `doctor` 项目健康检查。
- `.ai-board/config.json` 项目配置，支持默认语言、默认泳道、默认 agent 类型和默认租约。
- 生成看板支持中文 / 英文基础文案。
- `ai-board skills get core` 内置 AI 使用说明。
- GitHub Actions CI：ruff、Python 3.10/3.11/3.12 单元测试、wheel/sdist 构建。

### 调整

- 业务层预期错误改为使用 `BoardError`，不再主要依赖 `SystemExit`。
- `complete` 会释放任务拥有者的 agent 身份，同时保留任务历史 owner。
- scope 路径会做规范化，并拒绝绝对路径和跳出项目根的路径。
- `board.lock` 写入元数据，并支持 stale lock 恢复。
- Python 包元数据使用 `license = "MIT"`。

### 当前边界

- 这是 alpha 版本，不是稳定工作流引擎。
- scope lock 是路径级防撞，不理解代码语义。
- 依赖校验保持简单，不提供完整 planning graph。
- 暂未包含 SQLite 存储、`reopen`、更完整的 agent 恢复、PyPI 发布和静态类型检查。

### 发布前验证

- `ruff check .`
- `python -m unittest discover -s tests`
- `python -m build`
- `ai-board doctor --fail-on-issue`
- `ai-board conflicts --fail-on-conflict`
