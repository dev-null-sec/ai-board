# 更新日志

`ai-board` 的重要版本变化会记录在这里。以后 Release 说明和更新日志默认使用中文。

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
