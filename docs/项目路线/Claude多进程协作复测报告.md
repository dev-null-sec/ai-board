# Claude 多进程协作复测报告

日期：2026-05-15

## 目标

复测 `ai-board` 在真实 Claude Code 多进程协作中的表现，重点验证最近新增的三类约束是否有效：

- `start --scope` 能拒绝疑似把多个路径合成一个参数的情况。
- `inbox --fail-on-unresolved` 能在收口阶段发现未处理 notice。
- 内置指南能让 Claude 使用同一 agent 身份、窄 scope 和最新版本地 `ai-board`。

## 测试环境

- 临时项目：`tmp/claude-multi-agent-retest`
- Claude CLI：`2.1.121 (Claude Code)`
- `ai-board` 调用方式：`uv run --with-editable ..\.. ai-board`
- 基线项目：一个小型 Python 包 `sample_app`，初始 pytest 为 3 passed。

## 测试设计

临时项目中排了两个可并行任务：

- `T-0001 Add multiply math helper`
  - 目标文件：`sample_app/math_tools.py`
  - 测试文件：`tests/test_math_tools.py`
- `T-0002 Add text slug helper`
  - 目标文件：`sample_app/text_tools.py`
  - 测试文件：`tests/test_text_tools.py`

两个 Claude 进程同时用非交互方式运行：

- Agent A：处理 `T-0001`
- Agent B：处理 `T-0002`

每个进程都被要求先检查 `agents list`、`locks`、`next`，再 claim 身份、start 窄 scope、实现、测试、complete/archive，并在最后执行 `locks`、`conflicts --fail-on-conflict`、`inbox --fail-on-unresolved`。

## 实测过程

结构化事件日志显示：

- `claude-00` 于 `2026-05-15T09:23:55+00:00` claim，随后 start `T-0002`，scope 为 `sample_app/text_tools.py` 和 `tests/test_text_tools.py`。
- `claude-01` 于 `2026-05-15T09:24:51+00:00` claim，随后 start `T-0001`，scope 为 `sample_app/math_tools.py` 和 `tests/test_math_tools.py`。
- 两个任务 scope 不重叠，`conflicts --fail-on-conflict` 返回 `no conflicts`。
- `claude-01` 完成数学任务后向 `claude-00` 发送 `M-0001 [release]` notice。
- `claude-00` 初次结束时没有 resolve `M-0001`，`inbox --agent claude-00 --fail-on-unresolved` 返回非零，输出 `unresolved notices: 1`。
- 按 notice 响应流程再次调用 Claude B 后，`claude-00` 查询 `locks`、`show T-0001`、`conflicts --fail-on-conflict`，确认 notice 已满足，然后 resolve `M-0001` 并归档 `T-0002`。

## 额外防线探针

复测后新增一个探针任务 `T-0003 Scope merged argument rejection probe`，直接运行：

```powershell
uv run --with-editable ..\.. ai-board start T-0003 --agent probe --scope "sample_app/math_tools.py tests/test_math_tools.py"
```

结果符合预期：CLI 拒绝该参数，并提示如果是多个路径，应拆成多个 `--scope` 参数。这证明 `start --scope` 的空格误合并防线仍然有效。

## 最终结果

临时项目最终状态：

- `status`：`archived: 3`，其余当前状态均为 0。
- `locks`：`no locks`
- `conflicts --fail-on-conflict`：`no conflicts`
- `inbox --agent claude-00 --fail-on-unresolved`：`no notices`
- `inbox --agent claude-01 --fail-on-unresolved`：`no notices`
- `doctor --fail-on-issue`：`doctor: ok`
- `pytest`：5 passed

## 暴露的问题

这次复测不是完全平滑通过，反而验证了一个关键风险：Claude B 在第一次完成自身任务时，虽然运行了 `inbox --fail-on-unresolved` 并看到失败，但没有主动 resolve notice，也没有归档自己的 done 任务。

这说明：

- `--fail-on-unresolved` 作为机器可判定收口闸门是有用的，它确实抓住了未处理消息。
- 仅靠提示词要求“最后检查 inbox”还不够，agent 看到非零结果后未必会自动进入响应流程。
- 后续可以考虑让指南更明确：如果 `inbox --fail-on-unresolved` 返回非零，不能结束任务，必须 ack/resolve 或说明阻塞原因。

## 结论

这次复测证明当前多 agent 协作机制已经具备真实可用的基础闭环：

- 两个 Claude 进程能并行 claim 不同身份。
- 两个 Claude 进程能启动不重叠 scope 并完成各自代码任务。
- scope lock 和冲突检查能保持干净。
- notice 可以跨 agent 传递，并能被结构化日志追踪。
- `inbox --fail-on-unresolved` 能抓到未收口 notice。
- scope 空格误合并防线能拒绝高风险参数。

同时，这次复测也说明下一步应强化“失败后的标准动作”，尤其是把 `inbox --fail-on-unresolved` 的非零结果明确变成 agent 不得结束的硬性收口条件。
