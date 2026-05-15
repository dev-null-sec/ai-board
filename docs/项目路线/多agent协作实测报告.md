# 多 agent 协作实测报告

## 结论

这次不是理论推演，而是在 ai-board 自己的仓库里做过一次真实并行协作测试。

测试结果：两个 agent 在同一个工作区、同一份 `.ai-board/board.json` 上，同时推进两个不同任务，通过 task owner、scope lock、事件日志和 doctor/conflicts 检查完成协作。两个任务都完成并归档，没有出现 scope 冲突，也没有互相覆盖对方负责的文件。

这比“设计上支持多 agent”更有说服力：我们拿到了真实事件历史、真实锁范围、真实归档记录和真实验证命令。

## 测试背景

测试发生在 ai-board 自举开发过程中。当时用户要求继续推进项目，同时把这次推进当作多 agent 协作真实测试。

当时已有一个任务正在由 `codex-00` 推进：

- 任务：`T-0052 补齐计划看板自动渲染闭环说明和回归测试`
- owner：`codex-00`
- scope：`README.md`, `docs/当前状态.md`, `src/ai_board/skill_guides.py`, `tests/test_cli.py`

另一个 agent 没有抢这个任务，而是选择一个不冲突的任务推进：

- 任务：`T-0046 评估可选提交门禁和任务决策日志`
- owner：`codex-01`
- scope：`docs/项目路线/提交门禁和任务决策日志评估.md`

两个 scope 完全分离，因此适合并行。

## 实测时间线

时间为事件日志中的 UTC 时间。

### `codex-00` 推进 `T-0052`

```text
2026-05-15T03:17:06+00:00 task.add      T-0052
2026-05-15T03:17:14+00:00 task.schedule T-0052
2026-05-15T03:17:14+00:00 task.start    T-0052 agent=codex-00
2026-05-15T03:18:49+00:00 task.complete T-0052 agent=codex-00
2026-05-15T03:18:59+00:00 task.archive  T-0052 agent=codex-00
```

`T-0052` 的 scope：

```text
README.md
docs/当前状态.md
src/ai_board/skill_guides.py
tests/test_cli.py
```

### `codex-01` 推进 `T-0046`

```text
2026-05-15T02:03:08+00:00 task.add      T-0046
2026-05-15T03:18:14+00:00 task.schedule T-0046
2026-05-15T03:18:24+00:00 task.start    T-0046 agent=codex-01
2026-05-15T03:19:37+00:00 task.complete T-0046 agent=codex-01
2026-05-15T03:19:49+00:00 task.archive  T-0046 agent=codex-01
```

`T-0046` 的 scope：

```text
docs/项目路线/提交门禁和任务决策日志评估.md
```

## 并行重叠区间

`T-0052` 从 `03:17:14` active 到 `03:18:59` archived。

`T-0046` 从 `03:18:24` active 到 `03:19:49` archived。

两个任务在 `03:18:24` 到 `03:18:59` 之间同时 active，约 35 秒。这段时间内：

- `codex-00` 负责 README、当前状态、skill guide 和测试。
- `codex-01` 负责项目路线评估文档。
- 两边通过 scope lock 明确边界。
- `ai-board conflicts --fail-on-conflict` 返回 `no conflicts`。

## 验证命令

当时执行过的关键检查：

```powershell
ai-board locks
ai-board conflicts --fail-on-conflict
ai-board doctor --fail-on-issue
ai-board history T-0052
ai-board history T-0046
ai-board show T-0052
ai-board show T-0046
```

最终状态检查：

```text
ai-board conflicts --fail-on-conflict -> no conflicts
ai-board doctor --fail-on-issue -> doctor: ok
ai-board locks -> no locks
```

## 证明了什么

这次实测证明了几件事：

- 多 agent 可以在同一仓库里并行推进任务。
- `owner_agent` 能区分不同 agent 的责任边界。
- scope lock 能让 agent 主动避让，不需要靠聊天记忆猜测。
- 事件日志可以还原任务何时开始、由谁执行、何时完成和归档。
- 归档记录可以保留每个任务的验收结果和遗留问题。
- `conflicts` 和 `doctor` 能作为并行后的健康检查。

最关键的是：`codex-01` 没有抢 `codex-00` 的 active 任务，而是选择了不冲突的文档路线任务。这正是 ai-board 想解决的协作问题。

## 暴露的边界

这次也说明 ai-board 不是魔法沙箱：

- 它不能阻止 agent 绕过规则直接编辑文件。
- 它依赖 agent 在编码前运行 `locks`、`next`、`conflicts` 等命令。
- scope lock 是路径级防撞，不理解语义级冲突。
- 如果任务 scope 写得过宽，会降低并行空间。
- 如果生成 Markdown 过期，必须以 `.ai-board/board.json` 和 CLI 输出为准。

这些边界不削弱结论，反而让结论更可信：ai-board 提供的是轻量协作协议，不是沉重的权限系统。

## 可引用结论

可以在 README 或后续发布说明中这样描述：

> ai-board 的多 agent 协作不是只停留在设计上。项目自身已经用 `codex-00` 和 `codex-01` 在同一仓库内并行完成过两个 scope 不重叠的任务，事件日志记录了两个任务的 start、complete 和 archive，`conflicts` 与 `doctor` 检查均通过。

## 后续建议

- 保留这份报告作为项目真实 dogfood 证据。
- 后续 README 可以链接到本报告，而不是只抽象描述多 agent 能力。
- 继续鼓励新 agent 先运行 `ai-board next`，优先选择不冲突任务。
- 对外介绍时要说清楚：这是路径级协作防撞，不是代码合并或权限系统。
