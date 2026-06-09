# GSD Pi 对 ai-board 的战略校准

## 评估对象

本评估对象是 `open-gsd/gsd-pi`。

截至本次评估，GSD Pi README 对自己的定位是：

> local-first coding agent for planning, implementing, verifying, and tracking project work from the command line.

它的能力组合包括：

- terminal agent；
- project workflow tools；
- worktree-aware Git automation；
- local project memory；
- multi-provider model routing；
- extension surface；
- terminal / web surfaces。

这说明 GSD Pi 已经不是单纯的 prompt/workflow 包，也不是轻量任务看板，而是一个本地优先的 coding agent / control plane。

参考来源：

- `https://github.com/open-gsd/gsd-pi`
- `https://opengsd.net/products/gsd-pi`

## 核心判断

GSD Pi 的存在不要求 ai-board 改方向，反而进一步确认 ai-board 应该把边界钉死。

ai-board 不应该做成：

- coding agent；
- provider routing；
- terminal agent；
- TUI / Web control plane；
- extension marketplace；
- worktree executor；
- autonomous milestone runner。

ai-board 应继续定义为：

> agent-agnostic governance CLI：你继续使用 Claude、Codex、Cursor 或其他 AI；ai-board 只负责项目边界、任务事实源、scope、验证、审计和 git 关口。

换句话说：

- GSD Pi 试图接管“AI 如何干活”。
- ai-board 应该约束和记录“AI 干活前后必须留下什么事实”。

这是两条不同路线，不是同一赛道的轻重版本。

## 与 ai-board 的差异

| 维度 | GSD Pi | ai-board 应保持的边界 |
| --- | --- | --- |
| 产品形态 | 本地 coding agent / control plane | 本地治理 CLI |
| 执行方式 | agent 负责规划、实现、验证、推进 | 外部 agent 自己执行，ai-board 记录和约束 |
| 模型接入 | multi-provider model routing | 不接模型、不做 provider routing |
| Git 管理 | worktree-aware automation | git 关口和建议，不接管 worktree 执行 |
| 状态存储 | local project memory / database + markdown projections | `.ai-board/board.json` 继续作为当前真相源，后续重视 schema/migration |
| UI | terminal / web surfaces | CLI first，不做 Web/TUI 作为 1.0 目标 |
| 扩展 | extension surface | 保留轻量 skill discovery，不做扩展市场 |
| 多 agent | autonomous workflow / dispatch | 项目级可选，默认关，只做路径级防撞和审计 |

## 不应追的能力

### 不做 coding agent

ai-board 不应该内置模型调用、工具调用、代码修改或 autonomous execution。

理由：

- 一旦接管执行，就会和 Claude Code、Codex、Cursor、GSD Pi 正面重叠；
- 项目复杂度会从治理层变成 agent runtime；
- 当前最有价值的轻量性会被破坏；
- 用户已经有能写代码的 AI，缺的是稳定的事实源、验收和边界。

### 不做 provider routing

模型路由是 agent runtime 的能力，不是治理 CLI 的核心能力。

ai-board 可以记录“哪个 agent / 哪个会话 / 哪次任务”做了什么，但不应该负责选择模型、保存 API key 或路由请求。

### 不做 TUI / Web control plane

Web/TUI 很诱人，但不是 1.0 的关键。

ai-board 当前真正需要补的是：

- scope gate；
- verification evidence；
- human review；
- schema migration；
- planning continuity。

这些闭环没稳定前，做 UI 只会把精力转移到展示层。

### 不做扩展市场

GSD Pi 的 extension surface 适合 control plane。ai-board 只需要保持：

- CLI 命令稳定；
- skill discovery 简洁；
- `ai-board skills get core` 与版本同步。

扩展市场不是 ai-board 当前阶段的护城河。

## 可吸收的启发

### 1. Worktree：先做只读建议和 doctor 检查，不做执行器

GSD Pi 的 worktree-aware Git automation 是强机制，但 ai-board 不应照搬为自动 worktree 管理。

更适合 ai-board 的借鉴方式：

- `doctor` 检查当前是否在脏工作区推进高风险任务；
- `next` 对高风险或大 scope 任务建议使用 git branch / worktree；
- 多 agent 开启时，提醒不同 agent 使用隔离分支或工作树；
- `review` 汇总任务对应分支、提交和 scope 是否一致；
- 不自动创建、切换或合并 worktree，除非用户未来明确要求。

建议新增后续任务：

> 评估 git worktree / branch 隔离建议机制。

### 2. Usage / context observability：做治理指标，不做 token 计费器

GSD Pi 有 usage/context 观测能力。ai-board 不掌控模型调用，所以不应承诺精确 token 统计。

但 ai-board 可以做自己的治理指标：

- active/inbox/scheduled 数量是否过多；
- guide 是否过长；
- 当前状态是否过长或过旧；
- deferred verification 数量；
- blocked 任务滞留时间；
- scope 过宽次数；
- 越界 gate 命中次数；
- 任务完成后无验证证据次数；
- 多 agent notice 未收口次数。

这些指标比“token 计费”更符合 ai-board 定位：它们衡量项目治理是否变脏。

建议新增后续任务：

> 评估 ai-board usage/context observability 指标。

### 3. Local database + Markdown projection：加强 schema/migration，不急着换存储

GSD Pi 使用本地项目记忆和 Markdown 投影，这再次说明“真相源”和“人类阅读视图”分离是正确的。

ai-board 当前使用 `.ai-board/board.json` 作为唯一真相源，Markdown 看板只是生成视图，这个方向没错。

需要吸收的是长期可信度：

- schema 文档；
- migration；
- dry-run；
- 迁移前备份；
- 旧版本 board 回归测试；
- generated Markdown stale check。

暂不建议因为 GSD Pi 使用更重的本地存储，就马上把 ai-board 改为 SQLite。SQLite 可以继续作为未来评估项，但不是 1.0 前的必需转向。

### 4. Recovery / ship handoff：放进 review 与 verification evidence

GSD Pi 强调 recovery、verification evidence 和 ship handoff。

这对 ai-board 的启发是：

- `review` 不能只是事件历史；
- `complete/archive` 后仍应能看到“可交付摘要”；
- `deferred_verification` 和 leftovers 应该进入人类审计面；
- 任务归档后，仍要能快速回答“这次改动能不能交付”。

这部分应进入 0.4 human review 和 0.3 verification evidence。

## 是否调整 1.0 路线

结论：不调整 1.0 主路线。

当前 1.0 定义仍然成立：

> 一个本地优先、git 联动、可验证、可审计的 AI 项目治理 CLI。

但建议在路线解释里更强调一句：

> ai-board 不替代 coding agent，也不做 agent control plane；它服务于任何 AI 编码工具，负责事实源、scope、验证、审计和 git 边界。

这句话应该进入后续 README 定位文案。

## README 定位文案建议

建议 README 后续加入类似表述：

```text
ai-board is not a coding agent and does not replace Claude, Codex, Cursor, or GSD Pi.

It is an agent-agnostic governance CLI: you keep using your AI coding tool, while ai-board keeps the project work visible, scoped, verifiable, and reviewable.
```

中文可以写成：

```text
ai-board 不是 coding agent，也不替代 Claude、Codex、Cursor 或 GSD Pi。

它更像一层本地项目治理工具：你继续让 AI 写代码，ai-board 负责让需求进看板、scope 有边界、验收有证据、变更可审计。
```

## 建议新增后续任务

### 评估 git worktree / branch 隔离建议机制

目标：

- 不接管 worktree；
- 不自动切分执行；
- 只在 doctor/next/review 中给出隔离建议和风险提示。

验收方向：

- 高风险任务或宽 scope 时提示使用分支/worktree；
- 多 agent 开启时提示不同 agent 避免共用脏工作区；
- review 可展示任务关联 commit/branch 信息；
- 明确不做自动 merge/rebase。

### 评估 ai-board usage/context observability 指标

目标：

- 不做 token 计费器；
- 做项目治理健康度指标。

验收方向：

- 指标覆盖任务堆积、验证债务、过宽 scope、越界 gate、当前状态过长、guide 膨胀、notice 未收口；
- 判断这些指标属于 `doctor`、`review`、`status` 还是新命令；
- 给出不增加运行时依赖的实现方案。

## 最终判断

GSD Pi 是一个更完整、更重的本地 coding agent。

ai-board 不应该追它的大而全能力。ai-board 的机会在另一边：

- 不接管 AI；
- 不接管模型；
- 不接管 UI；
- 不接管 worktree 执行；
- 只把 AI 项目开发中最容易丢的事实、边界、验证和审计做扎实。

所以本次战略校准的结论是：

> GSD Pi 不是 ai-board 的路线模板，而是边界参照物。它提醒 ai-board 要更清楚地说明自己不是 agent，而是 agent-agnostic governance CLI。
