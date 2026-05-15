# Claude 多进程协作实测报告

## 结论

这次测试比前两次 Codex 自举协作更接近真实外部 agent 场景。

两个独立 Claude Code 进程在同一个临时项目里，靠 `ai-board` 完成了任务认领、scope 锁定、并行开发、验收归档，以及一次 notice 协作流程。最终临时项目 3 个任务全部归档，`conflicts`、`doctor` 和 `pytest` 都通过。

但测试也暴露出两个重要问题：

- 功能开发阶段不会自然触发 notice。两个 Claude 在不冲突任务上可以顺利并行，但没有主动产生跨 agent 消息。
- Claude 的自然语言总结偶尔会把身份说乱。报告必须以 `.ai-board/events.jsonl`、`.ai-board/messages.jsonl` 和 board 状态为准，不能只相信模型自述。

## 测试环境

主项目：

```text
D:\Backup\Documents\服务器远程运维\ai-board
```

临时测试项目：

```text
D:\Backup\Documents\服务器远程运维\ai-board\tmp\claude-multi-agent-test
```

Claude 版本：

```text
2.1.121 (Claude Code)
```

临时项目使用当前仓库 editable 版 `ai-board`：

```powershell
uv pip install --editable ..\..
```

测试中明确要求 Claude 使用：

```powershell
uv run ai-board ...
```

原因是裸 `ai-board` 可能指向用户级旧版命令，不一定包含 `tell`、`inbox`、`reopen`、`config` 等最新能力。

## 预置任务

临时项目中预置了 3 个任务：

- `T-0001 Agent A: extend math tools`
  - 预期修改 `sample_app/math_tools.py`、`tests/test_math_tools.py`。
- `T-0002 Agent B: extend text tools`
  - 预期修改 `sample_app/text_tools.py`、`tests/test_text_tools.py`。
- `T-0003 Agent C: shared verification notice drill`
  - 专门用于触发 `tell -> inbox -> ack -> board 校验 -> resolve`。

## 并行开发过程

监工并行启动两个 Claude 进程：

- `monitor/claude-00.log`
- `monitor/claude-01.log`

事件日志显示，两个 Claude 在同一时间段各自 claim 了身份：

```text
2026-05-15T07:29:49+00:00 agents.claim | agent=claude-00
2026-05-15T07:29:49+00:00 agents.claim | agent=claude-01
```

随后分别启动不重叠任务：

```text
2026-05-15T07:30:17+00:00 task.start | task=T-0002 | agent=claude-01 | scope=sample_app/text_tools.py,tests/test_text_tools.py
2026-05-15T07:30:32+00:00 task.start | task=T-0001 | agent=claude-00 | scope=sample_app/math_tools.py tests/test_math_tools.py
```

结果：

- `claude-01` 完成 `T-0002`，新增 `normalize_spaces(text)` 和测试。
- `claude-00` 完成 `T-0001`，新增 `multiply(left, right)` 和测试。
- 两个任务均 complete/archive。
- 最终全量测试从 4 条增加到 9 条并通过。

这一段证明了 `ai-board` 的身份池、task owner、scope lock 和归档流程能支撑两个外部 Claude 进程并行推进。

## Notice Drill

并行功能开发没有自然触发 notice，所以监工继续启动 notice drill，要求 Claude 围绕 `T-0003` 走一次消息流程。

事件日志显示：

```text
2026-05-15T07:36:13+00:00 task.start | task=T-0003 | agent=claude-00 | scope=.ai-board,monitor/claude-notice-sender.log
2026-05-15T07:36:44+00:00 message.tell | task=T-0003 | agent=claude-00 | message_id=M-0001
2026-05-15T07:37:12+00:00 message.tell | task=T-0003 | agent=claude-01 | message_id=M-0002
2026-05-15T07:37:38+00:00 message.ack | task=T-0003 | agent=claude-00 | message_id=M-0002
2026-05-15T07:38:39+00:00 message.resolve | task=T-0003 | agent=claude-00 | message_id=M-0002
2026-05-15T07:43:02+00:00 message.ack | task=T-0003 | agent=claude-01 | message_id=M-0001
2026-05-15T07:43:22+00:00 message.resolve | task=T-0003 | agent=claude-01 | message_id=M-0001
```

最终 `.ai-board/messages.jsonl` 中 3 条消息都已 ack/resolve：

- `M-0001`：`claude-00 -> claude-01`，request。
- `M-0002`：`claude-01 -> claude-00`，info。
- `M-0003`：`claude-00 -> claude-01`，info。

这证明最小 notice inbox 能完成：

- 可追溯发送。
- 接收方查看 inbox。
- 显式 ack。
- 以 `locks`、`show`、`conflicts` 校验 board 状态。
- 显式 resolve。

## 最终验收

临时项目最终状态：

```text
project: Claude multi-agent test
inbox: 0
scheduled: 0
active: 0
done: 0
archived: 3
blocked: 0
```

最终检查：

```text
locks: no locks
conflicts: no conflicts
doctor: ok
pytest: 9 passed
claude-00 inbox: no notices
claude-01 inbox: no notices
```

证据位置：

- `tmp/claude-multi-agent-test/monitor/*.log`
- `tmp/claude-multi-agent-test/.ai-board/events.jsonl`
- `tmp/claude-multi-agent-test/.ai-board/messages.jsonl`

## 哪些是 ai-board 生效

这些行为主要由 ai-board 机制约束出来：

- `agents claim --kind claude` 分配了 `claude-00`、`claude-01`。
- `start` 记录 owner 和 scope，阻止后续协作者无视当前 active 范围。
- `events.jsonl` 给出了可审计的 task 生命周期。
- `messages.jsonl` 给出了 notice 的发送、ack、resolve 证据。
- `doctor`、`locks`、`conflicts` 给了监工和 agent 共同的状态检查入口。
- `complete` / `archive` 让任务完成和释放身份成为显式动作。

## 哪些是监工介入

这些不是 ai-board 自动发生的，属于监工设计和推动：

- 创建临时项目和预置任务。
- 要求 Claude 必须使用 `uv run ai-board`。
- 并行启动两个 Claude 进程。
- 发现功能开发没有自然触发 notice 后，继续启动 `T-0003` notice drill。
- 发现 `M-0001`、`M-0003` 未 resolve 后，再启动一次收口检查。

这点很重要：当前 ai-board 可以让协作事实可见、可验证，但不会自动设计协作场景，也不会保证 agent 主动清空所有对方消息。

## 暴露的问题

### 1. Notice 不会自然出现

当两个任务 scope 明确且不冲突时，Claude 会直接完成任务，不一定发送 notice。

这不是 bug，反而说明 notice 应该只用于必要场景：

- 等待对方释放共享验证资源。
- 交接任务。
- 说明自己将缩小或释放 scope。
- 请求对方确认某个 board 状态。

不应要求所有任务都发 notice，否则会变成噪音。

### 2. 身份自述可能混乱

Claude 日志里出现过自然语言身份表述混乱。例如某段总结把 notice receiver 描述成 `claude-00`，但从事件和消息看，关键事实应以结构化记录为准。

这说明 agent 身份不能靠“我说我是 X”维持，需要 CLI 和提示词共同强化。

### 3. Scope 输入仍可能不够规范

事件里 `T-0001` 的 scope 记录成：

```text
sample_app/math_tools.py tests/test_math_tools.py
```

这看起来像把两个路径合成了一个参数。虽然本次没有造成冲突，但说明外部 agent 使用 CLI 时容易受 shell 参数写法影响。

后续应考虑让 `start --scope` 的示例更明确，或者在 CLI 层对包含空格的 scope 给出提醒。

### 4. Ack 和 resolve 需要更清晰的责任边界

第一次 notice drill 后，`M-0002` 已处理，但 `M-0001` 和 `M-0003` 仍未 resolve。后来通过收口检查才清空。

这说明协议还需要更明确：

- 收到发给自己的消息，自己负责 ack/resolve。
- 回复消息不等于自动 resolve 原消息。
- 任务 archive 前，应检查自己身份下是否仍有未处理 notice。

## 改进方向

### 短期

- 在 `ai-board skills get core` 里强调：正式协作中每个 agent 必须在开头记录“当前使用身份”，后续命令都用这个身份。
- 在 `complete` / `archive` 前建议 agent 跑 `inbox --agent YOUR_AGENT`，避免遗留未处理消息。
- 在报告和 README 中说明：notice 是必要时的协作提醒，不是每个任务都必须发送。
- 补一个任务清理 `T-0069`，它已被 `T-0070/T-0071/T-0072` 替代，继续 blocked 会误导后续 agent。

### 中期

- 给 CLI 增加 `whoami` 或 `agents current` 的轻量机制，让 agent 把“当前身份”写入本地会话文件或环境建议中。
- `next --agent` 已能提示 notice，后续可评估在 `complete` / `archive` / `unlock` 上提示该 agent 仍有未 resolved notice。
- 对 `start --scope` 增加校验：如果某个 scope 参数包含空格且不是现有路径，提示可能漏了引号或参数拆分错误。
- 增加 `inbox --agent AGENT --fail-on-unresolved`，便于收口检查和 CI 式验证。

### 暂不建议

- 不建议把 CLI 做成实时聊天系统。
- 不建议让 notice 自动修改 board 状态。
- 不建议引入强认证来证明某个消息一定来自某个模型进程；当前项目定位是轻量协作协议，不是安全边界。

## Agent 身份建议

当前身份模型是“协作身份”，不是安全身份。任何进程理论上都可以声称自己是 `claude-00`，所以它不能作为安全权限依据。

更实际的改进是让身份更难混乱：

1. Agent 开工第一步必须 `agents claim --kind KIND`。
2. CLI 返回的身份必须写进后续 prompt 或本轮任务笔记。
3. 所有 `start`、`tell`、`inbox`、`complete`、`archive` 都必须使用同一个身份。
4. 如果 agent 重启或另一个进程接手，必须重新 `agents list`，确认原身份 idle/busy/expired，再决定复用、等待或另 claim。
5. 报告里所有身份判断以 `events.jsonl` 和 `messages.jsonl` 为准，不以自然语言总结为准。

未来如果要做得更稳，可以考虑：

- `ai-board agents current --set AGENT`：把当前工作目录的推荐身份写到 `.ai-board/session.json`。
- `ai-board next` 在存在 current agent 时默认使用它。
- `ai-board start/complete/tell/inbox` 如果传入身份和 current 不一致，给出提醒。

这仍然不是强认证，但能显著减少“模型嘴上说错身份”的问题。
