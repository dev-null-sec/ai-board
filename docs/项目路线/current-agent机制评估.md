# current agent 机制评估

## 结论

建议做一个很轻的 `current agent` 便利层，但不要把它包装成认证机制。

合适边界是：

- 帮 agent 少传错 `--agent` / `--from`。
- 在身份不一致时给出提醒。
- 让 `next`、`inbox` 等读命令更容易默认到当前身份。
- 不证明“这个进程一定就是某个 agent”。
- 不替代 `agents claim`、task owner、scope lock、events、messages。

## 为什么需要

Claude 多进程实测暴露了一个问题：结构化记录是对的，但模型自然语言总结偶尔会说错自己是谁。

现在靠流程可以缓解：

1. 先 `agents claim --kind KIND`。
2. 记住返回的身份。
3. 后续 `start/tell/inbox/complete/archive` 都用同一个身份。

但外部 agent 很容易在长任务、重启、并行进程、复制 prompt 时把身份说乱。`current agent` 可以给 CLI 增加一个本地提醒点，让错身份更早暴露。

## 不解决什么

`current agent` 不解决安全问题。

任何本机进程都能读写项目文件，也可以调用：

```powershell
ai-board agents current --set claude-00
```

所以它不能用来做权限判断，也不能证明消息一定来自某个模型进程。

真正的事实源仍然是：

- `.ai-board/board.json` 中 task owner、scope、status。
- `.ai-board/events.jsonl` 中状态变化。
- `.ai-board/messages.jsonl` 中 notice 发送、ack、resolve。

## 存储位置

建议使用项目级本地文件：

```text
.ai-board/session.json
```

建议字段：

```json
{
  "current_agent": "codex-00",
  "updated_at": "2026-05-15T00:00:00+00:00",
  "note": "Convenience hint only; not authentication."
}
```

为什么不用全局用户配置：

- 同一台机器可能同时打开多个项目。
- 同一个项目可能由多个工具或终端并行操作。
- 项目级文件更容易随 `doctor`、`next`、`status` 一起解释。

为什么不放进 `board.json`：

- `board.json` 是团队共享的当前任务真相源。
- `current agent` 更像本地会话提示，放进 board 会让它看起来像协作事实。
- 如果多个会话同时改 current agent，反而会制造噪音。

`.ai-board/session.json` 如果将来进入实现，应考虑是否加入 `.gitignore` 或在文档里提示它是本地状态。当前项目已有 `.ai-board` 作为自举数据，默认不强行忽略；但对普通项目可以建议不提交 session 文件。

## 命令设计

最小命令建议：

```powershell
ai-board agents current
ai-board agents current --set AGENT
ai-board agents current --clear
```

行为：

- `agents current`：显示当前提示身份；没有则显示 `none`。
- `agents current --set AGENT`：校验该 agent 存在；如果不存在，提示先 `agents claim`。
- `agents current --clear`：清除当前提示身份。

暂不建议第一版自动 claim：

```powershell
ai-board agents current --claim-kind codex
```

原因是自动 claim 会模糊“申领身份”和“设置提示身份”的边界。第一版保持简单，先让 agent 明确 claim，再 set current。

## 与现有命令的关系

第一版只做提醒，不隐式改写参数。

建议提醒规则：

- `next` 如果没有传 `--agent`，但存在 current agent，可以提示：
  - `using current agent codex-00`
  - 然后按 `--agent codex-00` 显示 notice。
- `inbox` 如果没有传 `--agent`，可以在后续版本考虑使用 current agent；但第一版为了兼容，仍保留 `--agent` 必填，只在 help/guide 中建议。
- `start --agent X` 如果 current agent 是 Y 且 X != Y，打印 warning，不阻止。
- `tell --from X` 如果 current agent 是 Y 且 X != Y，打印 warning，不阻止。
- `complete/archive` 不直接传 agent，它们根据 task owner 判断；如果 task owner 和 current agent 不同，打印 warning，不阻止。

为什么不阻止：

- 可能是监工或维护者在替另一个 agent 收尾。
- 旧流程没有 current agent，强阻止会破坏兼容。
- 这个机制不是权限边界。

## Doctor 检查

可选增强：

- 如果 `session.json` 存在但不是合法 JSON，`doctor` 提醒。
- 如果 `current_agent` 不存在于 agents 池，`doctor` 提醒。
- 如果 `current_agent` 已 expired，`doctor` 提醒重新 claim 或 clear。

第一版实现时可以先不做 doctor，避免任务扩大。后续如果用户反馈 session 文件容易坏，再补。

## 风险

### 误以为是认证

这是最大风险。必须在 guide、help、文档中明确：

```text
current agent is a local convenience hint, not authentication.
```

中文说明：

```text
current agent 只是本地便利提示，不是认证或权限边界。
```

### 多进程覆盖

两个终端同时 `--set` 会互相覆盖 current agent。

这可以接受，因为 current agent 本来就是提示，不是事实。真正的并发事实仍看 active task owner 和 scope lock。

### 自动默认可能隐藏错误

如果命令自动使用 current agent，agent 可能不再显式传身份，日志可读性变差。

所以建议第一版只在 `next` 上使用 current agent 展示 notice，其它写命令只 warning，不自动补参数。

## 是否进入实现

建议进入实现，但分两步。

### 第一步

实现最小可用：

- `.ai-board/session.json`
- `agents current`
- `agents current --set AGENT`
- `agents current --clear`
- `next` 无 `--agent` 时可使用 current agent 展示 notice，并打印提示。
- `start/tell` 身份和 current 不一致时 warning，不阻止。

### 第二步

根据 dogfood 结果再考虑：

- `complete/archive` owner 与 current 不一致 warning。
- `doctor` 检查 session 文件。
- `inbox` 是否允许省略 `--agent`。

## 验收建议

如果排期实现，建议最小验收：

- 设置 current agent 后，`agents current` 能显示。
- 清除 current agent 后，显示 none。
- 设置不存在的 agent 会失败并提示先 claim。
- `next` 未传 `--agent` 时能使用 current agent 显示 notice。
- `start --agent other` 与 current 不一致时只 warning，不阻止。
- 单元测试覆盖 session 文件缺失、设置、清除、身份不一致 warning。

## 最终建议

做，但保持克制。

`current agent` 的价值是降低错身份概率，不是建立安全体系。它应该被描述成“本地便利提示”，并且所有真实判断仍回到 board、events、messages 和 scope lock。
