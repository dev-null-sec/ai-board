# 第二次多 agent 协作实测报告

## 结论

这次实测发生在共享验证资源和等待全量验收机制补齐之后。结果比第一次更有价值：两个会话不只是“各做各的”，而是已经能根据 active lock、scope 和任务边界主动避让。

本次协作中，`codex-00` 和 `codex-01` 在同一个仓库、同一份 `.ai-board/board.json` 上连续完成两段并行开发：

- 第一段：`codex-00` 推进 README/PyPI 发布文档修复，`codex-01` 并行推进时间解析函数去重。
- 第二段：`codex-00` 响应用户追加 FAQ，`codex-01` 并行补充 agent lease 过期的 doctor 提醒。

最终四个任务全部完成并归档，`conflicts` 和 `doctor` 均通过，没有出现抢 scope、覆盖对方文件或长期占用共享验证资源导致对方无法收尾的情况。

## 测试背景

这次测试不是事后构造，而是项目推进中自然发生的真实协作。

在上一轮协作暴露出“测试文件、核心 CLI 文件这类共享验证资源容易被长期占用”之后，项目补了两类约束：

- 任务可声明验证依赖范围和延后全量验收原因。
- `next`、`doctor` 和 AI 使用指南会提醒 agent 避免长期占用共享验证资源，并在释放后优先处理等待全量验收的任务。

这次实测正好验证这些约束有没有改变 agent 行为。结果是：有改变。新的会话开始时会先看 `locks` 和 `next`，看到另一个会话的 active scope 后，选择不重叠任务；追加 README FAQ 时，也先入池、归档当前任务、再重新认领 README 范围。

## 实测时间线

时间为 `.ai-board/events.jsonl` 中记录的 UTC 时间。

### 第一段并行：发布文档修复与代码质量修复

`codex-00` 处理 `T-0055`：

```text
2026-05-15T06:10:56+00:00 task.schedule T-0055
2026-05-15T06:11:01+00:00 task.start    T-0055 agent=codex-00
2026-05-15T06:14:20+00:00 task.complete T-0055 agent=codex-00
2026-05-15T06:14:27+00:00 task.archive  T-0055 agent=codex-00
```

`T-0055` scope：

```text
CHANGELOG.md
README.md
README_en.md
pyproject.toml
```

`codex-01` 处理 `T-0059`：

```text
2026-05-15T06:11:53+00:00 task.schedule T-0059
2026-05-15T06:12:12+00:00 task.start    T-0059 agent=codex-01
2026-05-15T06:14:05+00:00 task.complete T-0059 agent=codex-01
2026-05-15T06:14:13+00:00 task.archive  T-0059 agent=codex-01
```

`T-0059` scope：

```text
docs/当前状态.md
src/ai_board/datetime_utils.py
src/ai_board/operations.py
src/ai_board/store.py
```

两个任务从 `06:12:12` 到 `06:14:05` 同时 active，约 1 分 53 秒。一个改发布文档和 README，另一个改时间解析公共函数，scope 不重叠。

### 第二段并行：用户追加 FAQ 与 doctor 规则补充

`codex-00` 在用户追加 FAQ 后，没有直接把新需求混进 `T-0055`。它先新增 `T-0065`，等 `T-0055` 完成归档后再重新认领 README 范围：

```text
2026-05-15T06:14:02+00:00 task.add      T-0065
2026-05-15T06:14:45+00:00 task.schedule T-0065
2026-05-15T06:14:50+00:00 task.start    T-0065 agent=codex-00
2026-05-15T06:15:48+00:00 task.complete T-0065 agent=codex-00
2026-05-15T06:15:53+00:00 task.archive  T-0065 agent=codex-00
```

`T-0065` scope：

```text
README.md
README_en.md
```

`codex-01` 随后处理 `T-0037`：

```text
2026-05-15T06:15:42+00:00 task.schedule T-0037
2026-05-15T06:15:52+00:00 task.start    T-0037 agent=codex-01
2026-05-15T06:17:15+00:00 task.complete T-0037 agent=codex-01
2026-05-15T06:17:22+00:00 task.archive  T-0037 agent=codex-01
```

`T-0037` scope：

```text
docs/当前状态.md
src/ai_board/cli.py
tests/test_cli.py
```

这段最关键的细节是边界意识：`codex-00` 看到 `T-0037` 由 `codex-01` 持有后，在收尾时明确没有碰它的 scope；`codex-01` 也没有抢 README 任务。

## 验证结果

四个任务的归档记录里都有真实验证结果：

- `T-0055`：`uv build` 成功；检查 `PKG-INFO` 确认 PyPI long description 使用 GitHub/raw 绝对链接；`conflicts` 和 `doctor` 通过。
- `T-0059`：全量单元测试通过；`uv run --with ruff ruff check .` 通过；`conflicts` 和 `doctor` 通过。
- `T-0065`：`rg` 确认中英文 FAQ 存在；`conflicts` 和 `doctor` 通过。
- `T-0037`：focused doctor 测试、全量单元测试、ruff、`conflicts` 和 `doctor` 均通过。

本报告编写前再次检查：

```text
ai-board status -> active: 0
ai-board locks  -> no locks
ai-board next   -> 只剩后续 inbox 候选
```

## 这次证明了什么

这次比第一次实测多证明了一层东西：

- agent 会先看当前锁，不再默认“我能接就接”。
- 用户临时追加需求时，agent 会先入池，再按任务边界处理，而不是把新需求塞进正在收尾的任务。
- `codex-00` 与 `codex-01` 可以连续切换并行窗口，不只是在单个时间片里不冲突。
- 涉及 `tests/test_cli.py`、`src/ai_board/cli.py` 这类共享验证资源时，其他会话会识别这是别人正在处理的范围。
- 完成任务后及时归档释放锁，给下一段协作腾出空间。

这说明新增约束不只是写在文档里，它确实改变了 agent 的现场行为。

## 仍然暴露的边界

这次结果不错，但也说明几个边界还在：

- 避让仍然依赖 agent 先运行 `locks`、`next`、`doctor`，工具还不是强制的文件系统权限层。
- scope 写得越宽，并行空间越小；写得太窄，又可能漏掉真实会改的文件。
- 共享验证资源可以提醒和优先处理，但不能自动替 agent 决定“何时该停手释放”。
- 当前报告仍需要人工或 agent 主动归档，未来可以考虑让事件日志生成协作摘要草稿。

## 可引用结论

可以在 README、发布说明或路线文档里这样概括：

> ai-board 已完成第二次真实多 agent 协作实测。新约束上线后，`codex-00` 与 `codex-01` 在同一仓库内连续并行完成 README 发布修复、时间解析去重、FAQ 更新和 doctor 检查增强。两个会话根据 active lock 和 scope 主动避让，四个任务均完成归档，`conflicts` 与 `doctor` 检查通过。

## 后续建议

- 保留这份报告，作为“约束上线后确实改变协作行为”的证据。
- 后续如果继续做多 agent 测试，重点观察共享验证资源是否会被长期占用。
- 可以考虑增加 `ai-board report collaboration` 一类命令，从事件日志自动生成这种报告初稿。
- 对外介绍时继续说清楚：ai-board 是轻量协作协议，不是代码合并系统，也不是强权限沙箱。
