# GSD Pi vs ai-board 端到端对比测试报告

## 当前状态

测试已收口。最终公平比较采用 GSD Core + Claude Code 与 ai-board + Claude Code 两个成功样本，不再使用旧 GSD Pi headless 失败样本作为主结论。

GSD Pi 侧完成一次有效失败样本记录：GSD 能启动并识别模型，但 headless 执行没有创建 milestone/session，没有 tool calls，也没有修改业务文件。

ai-board 侧完成同一业务需求，并通过 CLI 验收、单元测试和 ai-board doctor。

后续用户认为直接拿 GSD Pi headless 失败结果收口不够公平，因此已改为补测 GSD Core。当前结论是：GSD Core 1.3.1 不是旧 `gsd --print` 模型 runner，而是安装到宿主 agent 的 workflow 资产和辅助命令；它需要由 Codex/Claude 这类宿主 agent 读取 workflow 后执行。

## Baseline

- seed commit: `71be1000f65154ae67c844a159a77abc20884069`
- GSD 目录: `tmp/gsd-vs-ai-board/run-gsd`
- ai-board 目录: `tmp/gsd-vs-ai-board/run-ai-board`

## GSD Pi 侧结果

- 工具版本: GSD Pi 1.1.1
- 模型: `custom-openai/gpt-5.5`
- 结果: 失败
- 业务文件改动: 无
- 工具状态/辅助文件改动: `.gitignore`、`.claude/settings.json`、`gsd-task.md`
- 验收: `--json` 参数仍不可用

详细证据见：

- `tmp/gsd-vs-ai-board/reports/gsd-transcript.md`

## GSD Core smoke 结果

- 工具版本: GSD Core 1.3.1
- 安装方式: `@opengsd/gsd-core@latest` 安装到隔离 smoke 项目的 `.codex/gsd-core`
- 安装状态: core workflow 和 `gsd-tools.cjs` 可用；installer 曾报告 `skills/gsd-*` 不完整，`.codex/skills` 为空
- 使用方式: 当前 Codex 会话读取并遵循 `.codex/gsd-core/workflows/fast.md`
- 结果: 通过
- 业务文件改动: `README.md`、`calc.py`、`tests/test_calc.py`
- 验收: 默认输出 `3`，JSON 输出 compact JSON，2 个 unittest 通过
- 提交: `140cae8 feat: add json output mode`

这个结果证明 GSD Core 作为宿主 agent 工作流可以跑通最小任务；它不证明 GSD Core 是一个独立 headless tool orchestrator。后续 Claude Code 评测需要改用 GSD Core workflow 口径，而不是旧 GSD Pi 的 `gsd --print` / headless 命令。

详细证据见：

- `tmp/gsd-vs-ai-board/reports/gsd-core-smoke-transcript.md`

## ai-board 侧结果

- 工具版本: ai-board 0.1.20
- 任务: `T-0001 给 calc CLI 增加 JSON 输出模式`
- 结果: 通过
- 业务文件改动: `README.md`、`calc.py`、`tests/test_calc.py`
- ai-board 产物: `.ai-board/`、`AGENTS.md`、`docs/`
- 验收: `--json` 参数可用，2 个 unittest 通过，`ai-board doctor` 通过

详细证据见：

- `tmp/gsd-vs-ai-board/reports/ai-board-transcript.md`

## 最终 token 观察

用户基于同类项目需求实测并提供了 usage 截图：

- GSD Core 侧：约 2.4M total tokens
- ai-board 侧：约 1.6M total tokens，输入约 68.5K，输出约 13.6K，57 requests，费用约 $1.5176

据此计算：

- ai-board 少用约 0.8M tokens
- ai-board 约少 33%
- GSD Core 约为 ai-board 的 1.5 倍

注意：这里记录的是 dashboard 观察值，不伪装成 provider CSV 导出。截图中的 total token 与可见 input/output 不是简单相加，本报告只记录观察到的 dashboard 总数，不虚构隐藏字段。

## 下一步评测口径

后续 CC 评测建议改成：

1. 重建干净的 GSD 对比目录，避免旧 `.claude`、`.gsd`、`.codex` 产物污染。
2. 在 GSD 目录安装 GSD Core 到目标宿主 agent 的本地配置。
3. 让 Claude Code 明确使用 GSD Core workflow 完成同一 calc 任务，优先测试小任务适配的 `fast` workflow。
4. ai-board 侧继续使用相同 seed 项目和相同需求。
5. 同时记录 token/cost、耗时、业务 diff、工具状态文件体量、人工干预次数和最终验收结果。

## GSD Core CC 评测准备

- 已重建目录：`tmp/gsd-vs-ai-board/run-gsd-core`
- 来源 seed commit：`71be1000f65154ae67c844a159a77abc20884069`
- 已安装 GSD Core 到 `.claude/`
- GSD Core 版本：1.3.1
- `node .\.claude\gsd-core\bin\gsd-tools.cjs --help` 已通过
- 安装产物已单独提交为基线：`c934c1a chore: add gsd core claude workflow assets`
- 当前 `run-gsd-core` 工作区干净，等待 Claude Code 执行业务任务
- GSD Core 侧提示词：`tmp/gsd-vs-ai-board/prompts/claude-gsd-core.md`
- ai-board 侧提示词：`tmp/gsd-vs-ai-board/prompts/claude-ai-board.md`

## GSD Core + Claude Code 侧结果

- 工具版本：GSD Core 1.3.1
- 宿主 agent：Claude Code
- 使用 workflow：`.claude/gsd-core/workflows/fast.md`
- 结果：通过
- 业务提交：`147a313 feat: add json output for add command`
- 业务文件改动：`README.md`、`calc.py`、`tests/test_calc.py`
- diff 规模：3 files changed, 23 insertions(+), 13 deletions(-)
- GSD 状态文件：业务任务期间未生成新的 `.claude` 文件，未生成 `.planning` 文件，`.planning/STATE.md` 不存在因此未更新
- 验收：
  - `uv run python calc.py add 1 2` 输出 `3`
  - `uv run python calc.py add 1 2 --json` 输出 `{"operation":"add","left":1,"right":2,"result":3}`
  - `uv run python -m unittest discover -s tests` 为 2 tests OK
  - 最终 git 工作区干净
- 人工干预：业务任务无人工实现干预

详细证据见：

- `tmp/gsd-vs-ai-board/reports/gsd-core-claude-transcript.md`

这个结果应作为刷新后的 GSD 侧有效完成样本。旧 GSD Pi headless 失败样本继续保留，但只能说明旧评测入口不适合当前公平对比，不能单独代表 GSD Core 能力。

## 最终结论

在这次小型确定性 CLI 任务上，两个工具都完成了需求并通过测试。

结论是：

- GSD Core 是更大的 workflow 系统，能跑通，但消耗更高。
- ai-board 是更窄的本地项目治理层，也能跑通，并且 token 更少。
- 对“已有 AI agent + 只需要任务、scope、验收、审计”的场景，ai-board 的轻量定位得到了这次实测支持。

最终报告见：

- `tmp/gsd-vs-ai-board/reports/final-report.md`
