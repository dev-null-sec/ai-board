# agent notice 通信评估

## 结论

建议 `ai-board` 承担一层很轻的 agent notice 职责，但不要做成实时聊天系统。

合适的边界是：CLI 保存和展示与任务、agent、scope 相关的协作提醒，让它们可追溯、可确认、可处理；不负责实时推送、不负责长对话、不替代 `board.json` 里的结构化任务状态。

这层能力应该先做最小版：

```text
ai-board tell --from AGENT --to AGENT|all --type info|wait|release|handoff|request [--task TASK_ID] MESSAGE
ai-board inbox --agent AGENT
ai-board inbox --agent AGENT --ack MESSAGE_ID
ai-board inbox --agent AGENT --resolve MESSAGE_ID
ai-board next --agent AGENT
```

其中 `next --agent` 只是在候选任务前提示未处理 notice，不自动改变任务状态。

## 为什么需要 notice

目前 ai-board 已经能通过 owner、scope lock、verify scope、doctor 和 next 避免硬抢任务。但实际协作还缺一层“意图提醒”：

- A 在等 B 释放 `tests/test_cli.py`，现在只能靠聊天记录说。
- A 已经不需要某个 scope，但如果忘了 `unlock`，B 只能等待。
- B 看到 A 的任务可能会受自己影响，却没有结构化方式说明“我还需要 2 分钟”。
- 用户临时要求多 agent 真实测试时，协作意图没有沉淀到事件里。

notice 可以补这个空白，但它不能成为新的事实源。真正的任务状态、锁和验收结果仍然以 `.ai-board/board.json` 为准。

## 送达语义

CLI 不能保证实时送达。

可承诺的语义应该是：

- 当 agent 以自己的身份调用支持 notice 的命令时，CLI 展示未处理 notice。
- 如果 agent 正在长时间思考、编辑或运行外部命令，CLI 无法打断它。
- notice 的可靠性来自“流程要求定期调用 CLI”，不是来自后台推送。

因此不要写“发送后对方会立刻收到”。应该写：

```text
next time codex-01 runs ai-board next --agent codex-01 or ai-board inbox --agent codex-01,
the notice will be shown.
```

## 触发点

建议第一版只在这些命令上展示 notice：

- `ai-board inbox --agent AGENT`
- `ai-board next --agent AGENT`
- `ai-board start --agent AGENT`
- `ai-board renew --agent AGENT`
- `ai-board complete --agent AGENT`
- `ai-board unlock --agent AGENT`

原因：

- 这些动作要么已经绑定 agent 身份，要么是接任务前的关键检查点。
- 它们是 agent 最应该看到协作提醒的地方。

暂不建议在普通 `status`、无身份 `next` 或无身份 `locks` 上展示个人 notice，因为 CLI 不知道消息应该给谁。

后续可以考虑全局身份来源：

```text
ai-board --agent codex-00 next
AI_BOARD_AGENT=codex-00
```

但第一版可以先只做命令级 `--agent`，降低改动范围。

## 身份来源与身份冒用

ai-board 当前是轻量协作协议，不是安全权限系统。任何会话理论上都可以声称自己是 `codex-00`。

notice 不应该假装解决安全认证问题。它只解决“协作事实可见、可追溯”：

- `--from` 应该默认使用当前 agent 身份。
- 如果允许显式 `--from`，也只能作为协作记录，不作为强认证。
- `tell` 可以检查 `from` 和 `to` 是否存在于 agents 列表，但不应把不存在视为严重错误；有些消息可能发给未来会 claim 的 agent。
- `to=all` 应该保留，但使用指南要提醒少用广播，避免噪音。

## ack 与 resolved

不建议只做 `read_at`。

“看到了”和“处理了”是两件事。如果 CLI 一展示就自动标已读，会造成假象：消息消失了，但 agent 可能没有行动。

建议字段：

```json
{
  "id": "M-0001",
  "from": "codex-00",
  "to": "codex-01",
  "type": "wait",
  "task_id": "T-0071",
  "message": "我在等 tests/test_cli.py，释放后请提醒",
  "created_at": "2026-05-15T00:00:00+00:00",
  "acknowledged_at": "",
  "resolved_at": ""
}
```

语义：

- `acknowledged_at`：我看到了。
- `resolved_at`：我已经处理完，比如释放锁、回复、确认无法处理或完成交接。

第一版可以只列未 resolved 的消息；`--ack` 和 `--resolve` 都需要显式执行。

## 消息类型

建议第一版固定枚举：

- `info`：普通提醒。
- `wait`：我在等你释放某个 scope 或完成某步。
- `release`：我已经释放或准备释放某个 scope。
- `handoff`：交接说明。
- `request`：请求你执行一个动作，比如缩小 scope、确认验证窗口、不要接某任务。

类型的作用是帮助 agent 做响应，不是自动执行动作。

## 消息与 board 冲突时谁说了算

永远以 board 为准。

例子：

- notice 说“我释放了 tests/test_cli.py”，但 `locks` 仍显示对方 active lock：以 `locks` 为准。
- notice 说“你可以接 T-0071”，但任务依赖未完成：以 `start` 的依赖检查为准。
- notice 说“我不改 cli.py 了”，但 active task scope 仍包含 `src/ai_board/cli.py`：仍视为被锁。

所以收到 notice 后，agent 的标准动作应该是先跑：

```text
ai-board locks
ai-board show TASK_ID
ai-board conflicts --fail-on-conflict
```

不能只根据消息内容直接编辑文件。

## 长任务期间收不到的问题

这是 CLI notice 的天然边界。

如果 agent 正在跑长测试、生成代码或进行长推理，它不会自动收到消息。要降低风险，流程上需要规定：

- 长任务前先 `inbox --agent AGENT`。
- 长任务中如需续租，用 `renew --agent AGENT`，并在续租时显示 notice。
- 完成、unlock、archive 前必须检查 notice。
- 持有共享验证资源时，定期 `renew` 或主动 `tell` 说明预计释放条件。

这比做后台守护进程更符合 ai-board 的轻量定位。

## 噪音控制

notice 如果太吵，agent 会忽略。

建议规则：

- 默认点对点，少用 `all`。
- `all` 广播只用于影响全局协作的事项，比如共享验证资源释放、重大锁变更。
- `next --agent` 只显示未 resolved 的前几条，可提示还有更多请运行 `inbox`。
- 消息正文保持短，不存长讨论。
- 长讨论应留在聊天或外部协作工具里，最终结论写回 board 或 docs。

## 非目标

第一版明确不做：

- 不做实时推送。
- 不做 WebSocket、后台 daemon 或桌面通知。
- 不做长对话频道。
- 不做权限认证系统。
- 不做自动根据消息 unlock、start、complete。
- 不把 notice 当任务状态源。

这些能力如果后续真的需要，应该另开项目或外置到桌面 app / 聊天系统，而不是塞进 CLI 核心。

## 存储建议

第一版可以用独立文件：

```text
.ai-board/messages.jsonl
```

理由：

- 避免把普通 notice 混进 `.ai-board/events.jsonl` 的任务生命周期事件里。
- JSONL 追加写适合消息。
- 读取简单，损坏时也容易定位到具体行。

同时可以在 `.ai-board/events.jsonl` 里记录概要事件：

```text
message.tell
message.ack
message.resolve
```

这样既保留消息详情，又能在 history 中看到关键协作动作。

## 最小实现范围

建议后续 `T-0071` 实现：

### 命令

```text
ai-board tell --from AGENT --to AGENT|all --type TYPE [--task TASK_ID] MESSAGE
ai-board inbox --agent AGENT
ai-board inbox --agent AGENT --ack MESSAGE_ID
ai-board inbox --agent AGENT --resolve MESSAGE_ID
ai-board next --agent AGENT
```

### 字段

```text
id
from
to
type
task_id
message
created_at
acknowledged_at
resolved_at
```

### 行为

- `tell` 追加消息，写 `message.tell` 事件。
- `inbox` 显示发给该 agent 和 `all` 的未 resolved 消息。
- `--ack` 只写 `acknowledged_at`。
- `--resolve` 写 `resolved_at`，必要时也补 `acknowledged_at`。
- `next --agent` 在 active locks 和候选任务前显示未 resolved notice 摘要。
- 消息显示不自动 ack。

### 测试

- 点对点消息能被目标 agent 看到。
- `all` 广播能被任意 agent 看到。
- 非目标 agent 看不到点对点消息。
- `ack` 后仍可见但标记为 acknowledged。
- `resolve` 后默认不再显示。
- `next --agent` 会显示未 resolved notice。
- 消息说释放但 board lock 未释放时，`locks` 仍显示锁，测试文案明确 board 为准。

## 推荐实施顺序

1. 完成 `T-0070` 评估，先冻结边界。
2. 做 `T-0071` 最小 notice inbox，不做实时聊天。
3. 做 `T-0072` 响应协议指南，规定收到 notice 后的动作。
4. 观察一次真实多 agent 协作，再决定是否需要更复杂的能力。

## 已固化的响应协议

`ai-board skills get core` 已补充收到 notice 后的固定动作：

- 先运行 `ai-board inbox --agent YOUR_AGENT` 读取未处理 notice。
- 按类型判断：`wait`、`release`、`handoff`、`request`、`info`。
- 只要涉及任务或 scope，就先跑 `locks`、`show TASK_ID`，必要时跑 `conflicts --fail-on-conflict`。
- 如果自己后续不再需要锁定 scope，就 `unlock`、`complete` 或 `archive`；如果还需要，就用 `tell` 回复原因和预计释放条件。
- 如果 notice 改变任务边界，必须通过 CLI 更新 board；notice 本身不是事实源。
- 读到后可以 `--ack`，处理、回复或确认无影响后再 `--resolve`。

## 可引用结论

> ai-board 可以承担轻量 agent notice 职责，但只作为协作提醒层。notice 负责把“我在等你释放 scope”“我已处理完交接”等短消息沉淀下来；真正的任务状态、锁、依赖和验收仍以 board 为准。CLI 不做实时聊天，不承诺即时送达，也不根据消息自动修改任务状态。
